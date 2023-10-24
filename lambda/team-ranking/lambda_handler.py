import boto3
import pandas as pd
import json
import time
import numpy as np

def run_query(query, database, s3_output):
    client = boto3.client('athena')
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            'Database': database
        },
        ResultConfiguration={
            'OutputLocation': s3_output,
        }
    )
    return response['QueryExecutionId']

def get_results(query_id):
    client = boto3.client('athena')
    
    while True:
        response = client.get_query_execution(QueryExecutionId=query_id)
        if response['QueryExecution']['Status']['State'] == 'SUCCEEDED':
            break
        elif response['QueryExecution']['Status']['State'] == 'FAILED':
            raise Exception("Athena query failed!")
        time.sleep(2)
    
    result = client.get_query_results(QueryExecutionId=query_id)
    return result

client = boto3.client('athena')

def recent_game_stats(team_ids):
    
    if isinstance(team_ids, (list, tuple)):
        team_ids_str = ', '.join(map(str, team_ids))
    else:
        team_ids_str = str(team_ids)
    
    query = f"""
WITH unnested_tournaments AS (
    SELECT 
        id AS league_id,
        region,
        tournament.id AS tournament_id
    FROM 
        lol.leagues
        CROSS JOIN UNNEST(tournaments) AS t (tournament)
),
tourney AS (
    SELECT * 
    FROM lol.tournaments
    WHERE startdate > '2001-01-01'
    AND startdate < '2023-12-12'
),
tourney_matches AS (
    SELECT 
        t.*,
        tr.region,  -- Adding the region column here
        stage.name AS stage_name,
        stage.type AS stage_type,
        stage.slug AS stage_slug,
        section.name AS section_name,
        match_item.id AS match_id,
        match_item.type AS match_type,
        match_item.state AS match_state,
        match_item.mode AS match_mode,
        match_item.strategy.type AS match_strategy_type,
        match_item.strategy.count AS match_strategy_count,
        team.id AS team_id,
        team.side AS team_side,
        team.record.wins AS team_wins,
        team.record.losses AS team_losses,
        team.record.ties AS team_ties,
        team.result.outcome AS team_outcome,
        team.result.gamewins AS team_gamewins,
        player.id AS player_id,
        player.role AS player_role
    FROM tourney t
    JOIN unnested_tournaments tr ON tr.tournament_id = t.id  -- Joining on the tournament_id to get the region
    CROSS JOIN UNNEST(stages) AS t (stage)
    CROSS JOIN UNNEST(stage.sections) AS s (section)
    CROSS JOIN UNNEST(section.matches) AS m (match_item)
    CROSS JOIN UNNEST(match_item.teams) AS tm (team)
    CROSS JOIN UNNEST(team.players) AS p (player)
),
teamWins AS (
    SELECT distinct team_id, lol.teams.slug, tourney_matches.region, lol.teams.name, acronym, team_wins, team_losses, team_ties, team_gamewins 
    FROM tourney_matches
    JOIN lol.teams 
    USING(team_id)
),
teamStats AS (
    select region, lol.teams.slug, teamWins.name, teamWins.acronym, team_id, sum(team_wins) as nwin, sum(team_losses) nloss
    from teamWins
    join lol.teams using(team_id)
    group by team_id, lol.teams.slug, region, teamWins.name, teamWins.acronym
)
SELECT * FROM teamStats

    """
    database = "lol"
    s3_output = "s3://query-results-144/a/Dont-bill-me/"
    query_id = run_query(query, database, s3_output)
    result = get_results(query_id)
    tourney_info = []
    headers = []
    for i, Rows in enumerate(result['ResultSet']['Rows']):
        if i == 0:
            for El in Rows['Data']:
                val = El['VarCharValue']
                headers.append(val)
            continue
        tourney_info.append({f'{header}':Rows['Data'][i]['VarCharValue'] for i,header in enumerate(headers)})
    return tourney_info

def lambda_handler(event, context):
    if not event.get('queryStringParameters') or 'team_ids' not in event['queryStringParameters']:
        return {
            'statusCode': 400,
            'body': json.dumps({"message": "Error: team_ids parameter is required."}),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            }
        }
    
    # If team_ids are provided, continue processing
    team_ids = event['queryStringParameters']['team_ids'].split(',')
    
    # Fetch recent game stats for the provided team_ids
    team_data = recent_game_stats(team_ids)
    
    df = pd.DataFrame(team_data)
    
    # Basic Metrics
    df['nwin'] = df['nwin'].astype(int)
    df['nloss'] = df['nloss'].astype(int)
    df['win_loss_ratio'] = df.apply(lambda row: row['nwin'] if row['nloss'] == 0 else row['nwin'] / (row['nwin'] + row['nloss']), axis=1)
    df['ntot'] = df['nwin'] + df['nloss']
    df['team_code'] = df['acronym']
    
    if event.get('queryStringParameters') and 'min_games_threshold' in event['queryStringParameters']:
        min_games_threshold = float(event['queryStringParameters']['min_games_threshold'])
    else:
        min_games_threshold = 10
        
    if event.get('queryStringParameters') and 'max_games_played' in event['queryStringParameters']:
        max_games_played = float(event['queryStringParameters']['max_games_played'])
    else:
        max_games_played = 50

    df['reliability_factor'] = np.clip(df['ntot'] / max_games_played, 0, 1)
    
    # Compute the weighted win-loss ratio formula with a logarithmic factor
    df['weighted_win_loss_ratio'] = df['win_loss_ratio'] * (1 + np.log1p(df['ntot'] / max_games_played))
    
    # Regional Strength Metrics
    grouped = df.groupby('region')
    top_teams_threshold = 5
    avg_win_loss_by_region = grouped.apply(lambda x: x.nlargest(top_teams_threshold, 'win_loss_ratio')['win_loss_ratio'].mean())
    total_games_by_region = df.groupby('region')['ntot'].sum()
    region_strength = 1.5 * avg_win_loss_by_region + 0.1 * (total_games_by_region / total_games_by_region.max())
    region_strength_normalized = region_strength / region_strength.sum()
    
    # International Performance Metrics
    international_df = df[df['region'] == 'INTERNATIONAL'].copy()
    international_df['original_region'] = international_df['name']
    regional_win_rates_international = international_df.groupby('original_region')['win_loss_ratio'].mean()
    
    # Comparison of Local vs. International Performance
    merged_df = df.merge(international_df[['team_id', 'win_loss_ratio']], on='team_id', how='left', suffixes=('_local', '_international'))
    merged_df['win_loss_ratio_international'].fillna(0, inplace=True)  # Fill NaN values with 0
    merged_df['performance_difference'] = merged_df['win_loss_ratio_international'] - merged_df['win_loss_ratio_local']
    
    # Applying additional weights before calculating final score.
    
    # for weighted_win_loss_ratio
    if event.get('queryStringParameters') and 'weight_wlr' in event['queryStringParameters']:
        weight_wlr = float(event['queryStringParameters']['weight_wlr'])
    else:
        weight_wlr = 0.5
        
    # weight for performance_difference
    if event.get('queryStringParameters') and 'weight_pd' in event['queryStringParameters']:
        weight_pd = float(event['queryStringParameters']['weight_pd'])
    else:
        weight_pd = 0.2
    
    df['raw_score'] = weight_wlr * df['weighted_win_loss_ratio'] + weight_pd * merged_df['performance_difference'].fillna(0)
    
    # Account for the reliability factor
    df['final_score'] = df['raw_score'] * df['reliability_factor']
    ranked_df = df.sort_values(by='final_score', ascending=False)
    ranked_df['rank'] = ranked_df['final_score'].rank(ascending=False, method='min')

    final_ranking = ranked_df.copy()
    
    # Filter the teams
    final_ranking = final_ranking[final_ranking['team_id'].isin(team_ids)]
    final_ranking = final_ranking[final_ranking['region'] != 'INTERNATIONAL']
    
    # Placeholder for missing teams
    missing_teams_list = [team for team in team_ids if team not in final_ranking['team_id'].values]
    missing_teams_df = pd.DataFrame({
        'team_id': missing_teams_list,
        'region': [None] * len(missing_teams_list),
        'slug': [None] * len(missing_teams_list),
        'name': [None] * len(missing_teams_list),
        'acronym': [None] * len(missing_teams_list),
        'nwin': [None] * len(missing_teams_list),
        'nloss': [None] * len(missing_teams_list),
        'win_loss_ratio': [None] * len(missing_teams_list),
        'ntot': [None] * len(missing_teams_list),
        'team_code': [None] * len(missing_teams_list),
        'weighted_win_loss_ratio': [None] * len(missing_teams_list),
        'reliability_factor': [None] * len(missing_teams_list),
        'raw_score': [None] * len(missing_teams_list),
        'final_score': [None] * len(missing_teams_list),
        'rank': [None] * len(missing_teams_list)
    })
    final_ranking = pd.concat([final_ranking, missing_teams_df], ignore_index=True)
    
    # Final_score and response
    final_ranking = final_ranking.sort_values(by='final_score', ascending=False).reset_index(drop=True)
    final_ranking['rank'] = final_ranking['final_score'].rank(method='min', ascending=False, na_option='bottom')

    response_data = [
        {
            "team_id": final_ranking.iloc[idx]['team_id'],
            "team_name": final_ranking.iloc[idx]['name'],
            "team_code": final_ranking.iloc[idx]['acronym'],
            "rank": idx + 1,

        }
        for idx in range(len(final_ranking))
    ]
    
    return {
        'statusCode': 200,
        'body': json.dumps(response_data),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        }
    }
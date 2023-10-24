import boto3
import pandas as pd
import json
import time
from datetime import datetime, timedelta

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

# collect the tournament itself
def get_tournament(id):
    query = f"""
    WITH tourney AS (
        SELECT * 
        FROM lol.tournaments
        WHERE id = '{id}'
    )
    SELECT id, leagueid, name, startdate, enddate from tourney
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
    
    if not tourney_info:
        raise ValueError(f"No tournament found for ID: {id}")

    start_date = datetime.strptime(tourney_info[0]['startdate'], '%Y-%m-%d')
    six_months_prior = start_date - timedelta(days=6*30)
    six_months_str = six_months_prior.strftime('%Y-%m-%d')
    tourney_info[0]['sixmonths'] = six_months_str

    return tourney_info[0]

    
# collect the tournament games
def get_tournament_matches(id):
    query = f"""
    WITH tourney AS (
        SELECT * 
        FROM lol.tournaments
        WHERE id = '{id}'
    ),
    tourney_matches AS (
        SELECT 
            t.*,
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
        FROM tourney
        CROSS JOIN UNNEST(stages) AS t (stage)
        CROSS JOIN UNNEST(stage.sections) AS s (section)
        CROSS JOIN UNNEST(section.matches) AS m (match_item)
        CROSS JOIN UNNEST(match_item.teams) AS tm (team)
        CROSS JOIN UNNEST(team.players) AS p (player)
    )
    SELECT distinct team_id, name, acronym, team_wins, team_losses, team_ties, team_gamewins 
    FROM tourney_matches
    JOIN lol.teams 
    USING(team_id)
    """
    database = "lol"
    s3_output = "s3://query-results-144/a/Dont-bill-me/"
    query_id = run_query(query, database, s3_output)
    result = get_results(query_id)
    tourney_matches = []
    headers = []
    for i, Rows in enumerate(result['ResultSet']['Rows']):
        if i == 0:
            for El in Rows['Data']:
                val = El['VarCharValue']
                headers.append(val)
            continue

        tourney_matches.append({f'{header}':Rows['Data'][i]['VarCharValue'] for i,header in enumerate(headers)})
    return tourney_matches

def recent_game_stats(team_ids, start_date, days=182):
    
    if isinstance(team_ids, (list, tuple)):
        team_ids_str = ', '.join(map(str, team_ids))
    else:
        team_ids_str = str(team_ids)
    
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    
    six_months_prior_obj = start_date_obj - timedelta(days=days)
    six_months_prior_str = six_months_prior_obj.strftime('%Y-%m-%d')
    
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
    WHERE startdate > '{six_months_prior_str}'
    AND startdate < '{start_date}'
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
    SELECT distinct team_id, tourney_matches.region, lol.teams.name, acronym, team_wins, team_losses, team_ties, team_gamewins 
    FROM tourney_matches
    JOIN lol.teams 
    USING(team_id)
),
teamStats AS (
    select region, teamWins.name, teamWins.acronym, team_id, sum(team_wins) as nwin, sum(team_losses) nloss
    from teamWins
    join lol.teams using(team_id)
    group by region, team_id, teamWins.name, teamWins.acronym
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

def league_comparison(start_date, days=182):
    
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    
    six_months_prior_obj = start_date_obj - timedelta(days=days)
    six_months_prior_str = six_months_prior_obj.strftime('%Y-%m-%d')
    
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
    WHERE startdate > '{six_months_prior_str}'
    AND startdate < '{start_date}'
),
tourney_matches AS (
    SELECT 
        t.*,
        tr.region,
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
region_game_count AS (
    SELECT 
        region,
        COUNT(DISTINCT match_id) AS games_played
    FROM tourney_matches
    GROUP BY region
)

SELECT * FROM region_game_count
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

def process_tourney(id):
    tourney = get_tournament(id)
    matches = get_tournament_matches(id)

    start_date = tourney['startdate']

    lc = league_comparison(start_date)

    teams = [x['team_id'] for x in matches]

    team_data = recent_game_stats(teams, start_date)

    df = pd.DataFrame(team_data)

    df['nwin'] = df['nwin'].astype(int)
    df['nloss'] = df['nloss'].astype(int)

    df['win_loss_ratio'] = df.apply(lambda row: row['nwin'] if row['nloss'] == 0 else row['nwin'] / (row['nwin'] + row['nloss']), axis=1)

    df['ntot'] = df['nwin'] + df['nloss']

    threshold = 10

    filtered_df = df[df['ntot'] >= threshold]

    filtered_df_sorted = filtered_df.sort_values(by=['win_loss_ratio', 'nwin'], ascending=[False, False])

    filtered_df_sorted.reset_index(drop=True, inplace=True)
    filtered_df_sorted = filtered_df_sorted[filtered_df_sorted['team_id'].isin(teams)]

    return filtered_df_sorted

def lambda_handler(event, context):
    
    if event.get('queryStringParameters') and 'tournament_id' in event['queryStringParameters']:
        tournament_id = int(event['queryStringParameters']['tournament_id'])
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Bad Request',
                'message': 'Missing tournament_id'
            })
        }
    
    ranked_teams = process_tourney(tournament_id)
    
    response_data = [
        {
            "team_id": ranked_teams.iloc[idx]['team_id'],
            "team_code": ranked_teams.iloc[idx]['acronym'],
            "team_name": ranked_teams.iloc[idx]['name'],
            "rank": idx + 1
        }
        for idx in range(len(ranked_teams))
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
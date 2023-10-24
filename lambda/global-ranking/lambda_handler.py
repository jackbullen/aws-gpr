import boto3
import pandas as pd
import json
import time

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

def lambda_handler(event, context):
    # Athena query
    query = """

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
    
    # Execute the query
    query_id = run_query(query, database, s3_output)
    result = get_results(query_id)

    team_dat = []
    headers = []

    # Extract the response form athena/boto3 query
    for i, Rows in enumerate(result['ResultSet']['Rows']):
        if i == 0:
            for El in Rows['Data']:
                val = El['VarCharValue']
                headers.append(val)
            continue
        team_dat.append({f'{header}':Rows['Data'][i]['VarCharValue'] for i,header in enumerate(headers)})
        
    # Store in pandas df  
    team_stats = pd.DataFrame(team_dat)
    
    team_stats["nwin"] = team_stats["nwin"].astype(int)
    team_stats["nloss"] = team_stats["nloss"].astype(int)
    
    team_stats["ntot"] = team_stats["nwin"] + team_stats["nloss"]
    team_stats["winp"] = team_stats["nwin"] / team_stats["ntot"]
    
    international_teams = team_stats[team_stats["region"] == "INTERNATIONAL"]
    
    domestic_counterparts = team_stats[team_stats["slug"].isin(international_teams["slug"]) & 
                                  (team_stats["region"] != "INTERNATIONAL")]

    agg_international_stats = international_teams.merge(domestic_counterparts[["slug", "region"]],
                                                       on="slug", 
                                                       suffixes=("_intl", "_domestic"))
    
    regional_international_winp = agg_international_stats.groupby("region_domestic")["winp"].mean().reset_index()

    regional_international_winp.columns = ["region", "international_winp"]
    
    LatinAmericaRegionalRating = float(regional_international_winp[regional_international_winp["region"] == "LATIN AMERICA"]['international_winp'])

    new_entries = [{"region": "LATIN AMERICA NORTH", "international_winp": LatinAmericaRegionalRating},
                   {"region": "LATIN AMERICA SOUTH", "international_winp": LatinAmericaRegionalRating}]

    regional_international_winp = pd.concat([regional_international_winp, pd.DataFrame(new_entries)], ignore_index=True)
    
    team_stats_with_regional_strength = team_stats.merge(regional_international_winp)

    # get a median strength for the regions that don't have international instances
    median_strength = regional_international_winp["international_winp"]
    
    team_stats_with_regional_strength = team_stats.merge(regional_international_winp, on="region", how="left")

    # for regions without international experience, fill with the median strength
    team_stats_with_regional_strength["international_winp"].fillna(median_strength, inplace=True)
    
    team_stats_with_regional_strength = team_stats_with_regional_strength[team_stats_with_regional_strength["region"] != "INTERNATIONAL"]
    
    team_stats_with_regional_strength["dominance"] = team_stats_with_regional_strength["nwin"] - team_stats_with_regional_strength["nloss"]
    team_stats_with_regional_strength["consistency"] = team_stats_with_regional_strength["winp"]
    team_stats_with_regional_strength["regional_strength"] = team_stats_with_regional_strength["international_winp"]

    
    if event.get('queryStringParameters') and 'dominance' in event['queryStringParameters']:
        dominance = float(event['queryStringParameters']['dominance'])
    else:
        dominance = 0.2
    
    if event.get('queryStringParameters') and 'consistency' in event['queryStringParameters']:
        consistency = float(event['queryStringParameters']['consistency'])
    else:
        consistency = 1.0
        
    if event.get('queryStringParameters') and 'regional_strength' in event['queryStringParameters']:
        regional_strength = float(event['queryStringParameters']['regional_strength'])
    else:
        regional_strength = 1.0
        
    if event.get('queryStringParameters') and 'streak_bonus' in event['queryStringParameters']:
        streak_bonus = float(event['queryStringParameters']['streak_bonus'])
    else:
        streak_bonus = 0.6
        
    if event.get('queryStringParameters') and 'streak_cutoff' in event['queryStringParameters']:
        streak_cutoff = float(event['queryStringParameters']['streak_cutoff'])
    else:
        streak_cutoff = 0.75
        
    if event.get('queryStringParameters') and 'underdog_bonus' in event['queryStringParameters']:
        underdog_bonus = float(event['queryStringParameters']['underdog_bonus'])
    else:
        underdog_bonus = 0.2
        
    if event.get('queryStringParameters') and 'int_underdog_cutoff' in event['queryStringParameters']:
        int_underdog_cutoff = float(event['queryStringParameters']['int_underdog_cutoff'])
    else:
        int_underdog_cutoff = 0.25
        
    if event.get('queryStringParameters') and 'reg_underdog_cutoff' in event['queryStringParameters']:
        reg_underdog_cutoff = float(event['queryStringParameters']['reg_underdog_cutoff'])
    else:
        reg_underdog_cutoff = 0.55
        
    weights = {
               "dominance": dominance, 
               "consistency": consistency, 
               "regional_strength": regional_strength, 
               "streak_bonus": streak_bonus, 
               "streak_cutoff": streak_cutoff, 
               "underdog_bonus": underdog_bonus,
               "int_underdog_cutoff": int_underdog_cutoff,
               "reg_underdog_cutoff": reg_underdog_cutoff
              }
    
    team_stats_with_regional_strength["base_score"] = (
        weights["dominance"] * team_stats_with_regional_strength["dominance"] +
        weights["consistency"] * team_stats_with_regional_strength["consistency"] +
        weights["regional_strength"] * team_stats_with_regional_strength["regional_strength"]
    )
    
    streak_bonus_mask = team_stats_with_regional_strength["winp"] > weights["streak_cutoff"]
    team_stats_with_regional_strength.loc[streak_bonus_mask, "base_score"] *= 1 + weights["streak_bonus"]
    
    underdog_mask = (team_stats_with_regional_strength["international_winp"] < weights['int_underdog_cutoff']) & (team_stats_with_regional_strength["winp"] > weights['reg_underdog_cutoff'])
    team_stats_with_regional_strength.loc[underdog_mask, "base_score"] *= 1 + weights["underdog_bonus"]
    
    ranked_teams_innovative = team_stats_with_regional_strength.sort_values(by="base_score", ascending=False)

    ranked_teams_innovative["rank"] = range(1, len(ranked_teams_innovative) + 1)

    ranked_teams = ranked_teams_innovative[["rank", "name", "acronym", "team_id", "base_score", "dominance", "consistency", "region", "international_winp"]]
    
    if event.get('queryStringParameters') and 'number_of_teams' in event['queryStringParameters']:
        number_of_teams = int(event['queryStringParameters']['number_of_teams'])
    else:
        number_of_teams = 10
    
    response_data = [
        {
            "team_id": ranked_teams.iloc[idx]['team_id'],
            "team_code": ranked_teams.iloc[idx]['acronym'],
            "team_name": ranked_teams.iloc[idx]['name'],
            "rank": int(ranked_teams.iloc[idx]['rank']),
            "base_score": float(ranked_teams.iloc[idx]['base_score']),
            "dominance": float(ranked_teams.iloc[idx]['dominance']),
            "consistency": float(ranked_teams.iloc[idx]['consistency']),
            "region": ranked_teams.iloc[idx]['region']
        }
        for idx in range(min(number_of_teams, len(ranked_teams)))
    ]
    
    return {
        'statusCode': 200,
        'body': json.dumps(response_data[:number_of_teams]),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            
        }
    }
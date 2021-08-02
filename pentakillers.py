import cassiopeia as cass 
import arrow
import pandas as pd
import time
import requests


'''
Go to https://developer.riotgames.com/ and create a LOGIN. After that, you'll be taken to a screen with the API key. 
There are 3 types of API keys in Riot Games:
- Development API (which is the default once you create a developer account): it's a key that needs to be refreshed every 24h
- Personal API: after registering a product (I didn't do it, so the API I've been using is Development), you don't need to 
    refreseh your api key. There are some restrcitions in the access (such as how many calls per minute/hour etc)
- Production API: this is for a real product, deployed, etc. I didn't even read details about it because it's way out of 
    the scope of this project.
You can get reference for them in https://developer.riotgames.com/docs/portal#product-registration_application-process
'''

API_KEY = "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx"
REGION = 'NA' # can be any region (NA, BR, TR, etc)


def get_curr_data(pentakiller, kill, start_time,):
    '''
    This function returns the requested info from the pentakiller (items, position, timestamp, etc)
    '''
    curr_data = {
        "summoner": pentakiller['summoner'], 
        "match id": pentakiller['match'], 
        "champion": pentakiller['champion'],
        "region": REGION,
        "x_pos": tuple(kill.get('position').values())[0],
        "y_pos": tuple(kill.get('position').values())[1],
        "item_1": list(map(lambda x: x if x else "empty slot", pentakiller.get("items")))[0],
        "item_2": list(map(lambda x: x if x else "empty slot", pentakiller.get("items")))[1],
        "item_3": list(map(lambda x: x if x else "empty slot", pentakiller.get("items")))[2],
        "item_4": list(map(lambda x: x if x else "empty slot", pentakiller.get("items")))[3],
        "item_5": list(map(lambda x: x if x else "empty slot", pentakiller.get("items")))[4],
        "item_6": list(map(lambda x: x if x else "empty slot", pentakiller.get("items")))[5],
        "timestamp": start_time
    }
    return curr_data
    
   
def new_kills_heatmap(self):
    '''
    I am MonkeyPatching the cassiopedia.core.match.Match.kills_heatmap method (because originally it didn't return the FIG image)
    Now that it is being returned, I can save to a file. That method was already written by the developers of the 
    cassiopedia module, and I'm simply updating it for our needs.
    '''
    if self.map.name == "Summoner's Rift":
        rx0, ry0, rx1, ry1 = 0, 0, 14820, 14881
    elif self.map.name == "Howling Abyss":
        rx0, ry0, rx1, ry1 = -28, -19, 12849, 12858
    else:
        raise NotImplemented

    imx0, imy0, imx1, imy1 = self.map.image.image.getbbox()

    def position_to_map_image_coords(position):
        x, y = position.x, position.y
        x -= rx0
        x /= (rx1 - rx0)
        x *= (imx1 - imx0)
        y -= ry0
        y /= (ry1 - ry0)
        y *= (imy1 - imy0)
        return x, y

    import matplotlib.pyplot as plt
    size = 8
    fig = plt.figure(figsize=(size, size)) # updated this line
    plt.imshow(self.map.image.image.rotate(-90))
    for p in self.participants:
        for kill in p.timeline.champion_kills:
            x, y = position_to_map_image_coords(kill.position)
            if p.team.side == cass.data.Side.blue:
                plt.scatter([x], [y], c="b", s=size * 10)
            else:
                plt.scatter([x], [y], c="r", s=size * 10)
    plt.axis('off')
    plt.show()
    
    return fig # added this line

cass.core.match.Match.kills_heatmap = new_kills_heatmap # updating the method


def setup(key, region):
    '''
    Basic setups for the cassiopedia module - logging, API_KEY and REGION
    '''
    cass.apply_settings({"logging": {
            "print_calls": False,
            "print_riot_api_key": False,
            "default": "WARNING",
            "core": "WARNING"
        }})
    cass.set_riot_api_key(API_KEY)
    cass.set_default_region(REGION)


def get_week_matches(summoner):
    '''
    This function takes the 'summoner' object and returns the match history for the period of 7 days that the summoner played
    '''
    now = arrow.utcnow()
    last_week = now.shift(days=-7)

    since = last_week.floor('day')
    until = now.floor('day')
    
    matches = cass.get_match_history(summoner, begin_time=since, end_time=until)
    
    return matches


def get_uri_region(region=REGION):
    mapping = {
        'BR':'BR1',
        'EUNE':'EUN1',
        'EUW':'EUW1',
        'JP':'JP1',
        'KR':'KR',
        'LAN':'LA1',
        'LAS':'LA2',
        'NA':'NA1',
        'OCE':'OC1',
        'TR':'TR1',
        'RU':'RU'
    }
    return mapping.get(region)


def get_diamonds(page, tier):
    '''
    Generator for diamond players. Since there's no implementation in the module Cass for diamond (and the # of players is vast), I 
    created this function. Handle with care not overload the server with thousands of requests.
    '''
    headers_dict = {"X-Riot-Token": API_KEY}
    region_api = str.lower(get_uri_region(REGION))
    URL = f"https://{region_api}.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/DIAMOND/{tier}?page={page}"
    response = requests.get(URL, headers=headers_dict)
    players_list = map(lambda x: x.get('summonerId'), response.json())
    for player in players_list:
        yield player


def get_masters():
    '''
    Generator for all masters in 'master league'
    '''
    masters = cass.get_master_league(queue=cass.Queue.ranked_solo_fives)
    for master in masters:
        yield master


def get_grandmasters():
    '''
    Generator for all grandmasters in 'grandmaster league'
    '''
    grandmasters = cass.get_grandmaster_league(queue=cass.Queue.ranked_solo_fives)
    for gm in grandmasters:
        yield gm


def get_challengers():
    '''
    Generator for all challengers in 'challenger league'
    '''
    challengers = cass.get_challenger_league(queue=cass.Queue.ranked_solo_fives)
    for challenger in challengers:
        yield challenger


def get_participant_info(match):
    '''
    This function generates a dictionary with the required data from a match if it had a pentakill
    '''
    pentakiller = None
    for participant in match.participants:
        if participant.stats.largest_multi_kill >= 5:
            pentakiller = {
                'summoner':participant.summoner.name,
                'match':match.id,
                'region':match.region.value,
                'champion':participant.champion.name,
                'participant':participant,
                'participant_id':participant.id,
                'items':list(map(lambda x: x.name if x is not None else None, participant.stats.items)),
            }
    return pentakiller


def get_kills_dict(participant_no, match_id):
    '''
    This function takes the match that had the kill and the participant that had the pentakill. 
    It then access the 'frames' of that match's timeline and creates a list of dictionaries of frames events (kills, drops, items built, etc)
    Then I only keep the events that had the property 'killerId' (which means it's a kill that a player did, and not a NPC) and
    filter only CHAMPION_KILLS (so PvP, and not PvE, for instance). 
    Then I save into kills_list and return that information
    '''
    
    kills_list = []
    events = []
       
    match = cass.get_match(match_id)
    
    for frame in match.timeline.frames:
        events.extend([x.to_dict() for x in frame.events])

    kill_events = [x for x in events if 'killerId' in x]
    kills = filter(lambda x: x['killerId']==participant_no and x['type']=='CHAMPION_KILL', kill_events)
    kills_list += kills
    
    return kills_list


def get_pentakill(kills_list):
    '''
    According to LoL wiki, the kills interval must be under 10 seconds until the 4th kill and then 30s (max) in the 5th kill.
    That way, I'm looping through all kills and checking if the next 1, 2, 3 and 4 kills are in the time range in relation to 
    the 0, 1, 2 and 3 kill. The timestamp comes in miliseconds, so I have to multiply by 1000.
    When it finds a group of 5 kills that fits the restrictions, breaks out of the loop and returns the first kill.
    '''
    for i, kill in enumerate(kills_dict):
        if all([(kills_dict[i+4]['timestamp'] - kills_dict[i+3]['timestamp'] <= 1000 * 30),
               (kills_dict[i+3]['timestamp'] - kills_dict[i+2]['timestamp'] <= 1000 * 10),
               (kills_dict[i+2]['timestamp'] - kills_dict[i+1]['timestamp'] <= 1000 * 10),
               (kills_dict[i+1]['timestamp'] - kills_dict[i]['timestamp'] <= 1000 * 10)]):
            break
    return kill


def generate_heatmap(match_id):
    '''
    Simple function that takes the match_id and saves the heatmap with the match_id in the filename.
    '''
    match = cass.get_match(match_id)
    fig = match.kills_heatmap()
    fig.savefig(f"{match_id}_heatmap.png")    


setup(API_KEY, REGION)


print('Fetching data for Challengers League:\n')
counter = 0 # I added a counter so we could stop early if we wanted 
MATCH_LIST = [] # this match_list is a list where I append all matches that are processed. That way, we can avoid repeated calls for similar matches
PENTAKILLERS_LIST = [] # a list with data from matches that happened to have pentakills

players = get_challengers() # assigned the challengers generator to the variable 'players'
player = next(players, None) # tried to retrieve the next challenger. if the generator is exhausted, this will return None

while player: # loops until the challengers generator is exhausted
    counter += 1
    
    print(f"\n{counter}. Evaluating Player: {player.summoner.name}")
    
    matches = get_week_matches(player.summoner)
    
    if not matches:
        print(f"No matches in the last 7 days for {player.summoner.name}")
        player = next(players, None)
        continue
    
    for i, match in enumerate(matches):
        print(f"Fetching data for Match {i+1}/{len(matches)}")
        
        if MATCH_LIST.count(match.id):
            print("Already fetched this Match")
            continue
        
        MATCH_LIST.append(match.id)
        pentakillers = get_participant_info(match)
        if not pentakillers:
            print(f"Match {match.id} did not have any pentakillers...")
            continue
        
        print(f"Pentakillers on Match {match.id}: {pentakillers}")
        PENTAKILLERS_LIST.append(pentakillers)
        
    
    print(f"Finished fetching data for Player: {player.summoner.name}")
    
    print('\n--- Waiting 5 seconds to start next Player ---\n') # this is to try to avoig making too many requests and being interrupted
    time.sleep(5)

    player = next(players, None)
    
    if counter == 50:
        break

print("Finished fetching data for Challenger League.\n")

print('Fetching data for GrandMasters League:\n')
counter = 0 
players = get_grandmasters() # assigned the grandmasters generator to the variable 'players'
player = next(players, None) # tried to retrieve the next grandmaster. if the generator is exhausted, this will return None

while player: # loops until the challengers generator is exhausted
    counter += 1
    
    print(f"\n{counter}. Evaluating Player: {player.summoner.name}")
    
    matches = get_week_matches(player.summoner)
    
    if not matches:
        print(f"No matches in the last 7 days for {player.summoner.name}")
        player = next(players, None)
        continue
    
    for i, match in enumerate(matches):
        print(f"Fetching data for Match {i+1}/{len(matches)}")
        
        if MATCH_LIST.count(match.id):
            print("Already fetched this Match")
            continue
        
        MATCH_LIST.append(match.id)
        pentakillers = get_participant_info(match)
        if not pentakillers:
            print(f"Match {match.id} did not have any pentakillers...")
            continue
        
        print(f"Pentakillers on Match {match.id}: {pentakillers}")
        PENTAKILLERS_LIST.append(pentakillers)
        
    
    print(f"Finished fetching data for Player: {player.summoner.name}")
    
    print('\n--- Waiting 5 seconds to start next Player ---\n') # this is to try to avoig making too many requests and being interrupted
    time.sleep(5)

    player = next(players, None)
    
    if counter == 50:
        break
        
print("Finished fetching data for GrandMaster League.\n") 

print('Fetching data for Masters League:\n')
counter = 0 
players = get_masters() # assigned the challengers generator to the variable 'players'
player = next(players, None) # tried to retrieve the next master. if the generator is exhausted, this will return None

while player: # loops until the challengers generator is exhausted
    counter += 1
    
    print(f"\n{counter}. Evaluating Player: {player.summoner.name}")
    
    matches = get_week_matches(player.summoner)
    
    if not matches:
        print(f"No matches in the last 7 days for {player.summoner.name}")
        player = next(players, None)
        continue
    
    for i, match in enumerate(matches):
        print(f"Fetching data for Match {i+1}/{len(matches)}")
        
        if MATCH_LIST.count(match.id):
            print("Already fetched this Match")
            continue
        
        MATCH_LIST.append(match.id)
        pentakillers = get_participant_info(match)
        if not pentakillers:
            print(f"Match {match.id} did not have any pentakillers...")
            continue
        
        print(f"Pentakillers on Match {match.id}: {pentakillers}")
        PENTAKILLERS_LIST.append(pentakillers)
        
    
    print(f"Finished fetching data for Player: {player.summoner.name}")
    
    print('\n--- Waiting 5 seconds to start next Player ---\n') # this is to try to avoig making too many requests and being interrupted
    time.sleep(5)

    player = next(players, None)
    
    if counter == 50:
        break
        
print("Finished fetching data for Master League.\n") 

print('Fetching data for Diamond League:\n')
counter = 0 
players = get_diamonds(page=1, tier='I') # assigned the challengers generator to the variable 'players'
player = next(players, None) # tried to retrieve the next diamond. if the generator is exhausted, this will return None

while player: # loops until the challengers generator is exhausted
    counter += 1
    
    summoner = cass.get_summoner(id=player)
    print(f"\n{counter}. Evaluating Player: {summoner.name}")
    
    matches = get_week_matches(summoner)
    
    if not matches:
        print(f"No matches in the last 7 days for {summoner.name}")
        player = next(players, None)
        continue
    
    for i, match in enumerate(matches):
        print(f"Fetching data for Match {i+1}/{len(matches)}")
        
        if MATCH_LIST.count(match.id):
            print("Already fetched this Match")
            continue
        
        MATCH_LIST.append(match.id)
        pentakillers = get_participant_info(match)
        if not pentakillers:
            print(f"Match {match.id} did not have any pentakillers...")
            continue
        
        print(f"Pentakillers on Match {match.id}: {pentakillers}")
        PENTAKILLERS_LIST.append(pentakillers)
        
    
    print(f"Finished fetching data for Player: {summoner.name}")
    
    print('\n--- Waiting 5 seconds to start next Player ---\n') # this is to try to avoig making too many requests and being interrupted
    time.sleep(5)

    player = next(players, None)
    
    if counter == 50:
        break
        
print("Finished fetching data for Diamond League.\n") 


data = []
'''
general printing and returning images for the pentakills
'''
for pentakiller in PENTAKILLERS_LIST:
    
    print(f"Fetching data for Pentakiller '{pentakiller['summoner']}' in Match {pentakiller['match']}:")
    print("Generating kills heatmap...",end=' ')
    generate_heatmap(pentakiller['match'])
    print("Done!")
    
    kills_dict = get_kills_dict(pentakiller['participant_id'], pentakiller['match'])
    kill = get_pentakill(kills_dict)
    minutes = kill['timestamp']//60000
    seconds = int(60*(kill['timestamp']/60000 - minutes))
    start_time = f"{minutes:02}:{seconds:02}"
    print(f"The Pentakill started at the {start_time} mark, with coordinates {tuple(kill.get('position').values())}.")
    print(f"The player finished the game with the following items:\n{pentakiller.get('items')}")
    
    data.append(get_curr_data(pentakiller, kill, start_time))
    print('\n')


# exporting datat to a csv file.
pd.DataFrame(data).to_csv('pentakills.csv', index=False, header=True, encoding='utf-8')




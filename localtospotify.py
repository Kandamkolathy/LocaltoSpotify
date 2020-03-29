import eyed3
import os 
import requests
import json
import webbrowser
import http.server
import sys
from io import StringIO
import base64
import urllib.parse

CLIENT_ID = "128418d86c274651af8cdc709df1c143"
CLIENT_SECRET = "338ea240ab8d477ab9d799631406afb9"

def main():
    unsuccesful = []    #Unsuccesful track transfers
    store = []          #Track location
    p = 0               #Progress Bar iterator
    i = 0               # Reused Iterator
    songlist = ""
    auth = ''           #Authrorization code
    empty = 0           #Used to check for failed track transfers
    listlen = 0         #Number of tracks
    untagged = []       #Files without proper ID3 tagging

    directory = input('Music directory: ')
    existingstate = input('Exisiting or New Playlist: ')
    while existingstate != 'New' and "new" and "N" and "n" and "Existing" and "existing" and "Exists" and "exists" and "E" and "e" and "Exist" and "exist":
        existingstate = input('Exisiting or New Playlist: ')
    playlistname = input('Playlist name: ')
    
    result = authenticate()
    result_string = result.getvalue()

    #Store file locations
    directoryencode = os.fsencode(directory)
    gettracks(directoryencode,store)

    printProgressBar(0, len(store), prefix = 'Progress:', suffix = 'Complete', length = 50)

    # Iterate through server output to retrive authentication code
    while result_string[i] != '=':
        i += 1
    i += 1

    while result_string[i] != ' ':
        auth = auth + result_string[i]
        i += 1
    i = 0

    #Send request to retrive access token using auth code
    params = {
        "grant_type": "authorization_code",
        "code": auth,
        "redirect_uri": "http://localhost:8000",
    }
    headers = {  
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization" : "Basic " + base64.b64encode("{}:{}".format(CLIENT_ID, CLIENT_SECRET).encode('UTF-8')).decode('ascii')
    }
    html = requests.request('post', "https://accounts.spotify.com/api/token", headers=headers, params=params, data=None) 
    token = html.json()

    # Final access token form for use in api calls
    auth = 'Bearer ' + token['access_token']


    while i < len(store):

        printProgressBar(p + 1, len(store), prefix = 'Progress:', suffix = 'Complete', length = 50)
        p += 1

        #If track failed don't add comma seperator to list
        if i > 0 and empty != 1:
            songlist = songlist + "%2C"
        empty = 0   

        #Stop eyed3 error ouputs
        sys.stderr = result

        #Get search terms through tags
        song = eyed3.core.load(store[i])
        songname = song.tag.title
        album = song.tag.album
        artist = song.tag.artist
        
        #Skip files without tags
        if songname == None or album == None:
            untagged.append(store[i])
            i += 1
            continue
        
        sys.stderr = sys.__stderr__

        #Encode search terms for URL usage
        songname = urllib.parse.quote(songname,safe='')
        album = urllib.parse.quote(album,safe='')
        artist = urllib.parse.quote(artist,safe='')

        #Api call for track search using track name and album
        response = requests.get("https://api.spotify.com/v1/search?q=track:"+ songname +"%20album:"+ album +"&type=track&limit=1", headers = {'Authorization' : auth})
        dictionary = response.json()

        #If previous check failed replace album with artist
        if dictionary['tracks']['items'] == []:
            if artist == None:
                untagged.append(store[i])
                i += 1
                continue
            response = requests.get("https://api.spotify.com/v1/search?q="+ songname +"%20artist:"+ artist +"&type=track&limit=1", headers = {'Authorization' : auth})
            dictionary = response.json()
        
        #If both failed add track to unsuccesful array and continue
        if dictionary['tracks']['items'] == []:
            unsuccesful.append(urllib.parse.unquote(songname))
            i += 1
            empty = 1
            continue

        #Add retrived track id to list
        trackid = dictionary['tracks']['items'][0]['id']
        songlist = songlist + "spotify%3Atrack%3A" + trackid
        listlen += 1
        
        i += 1
    i = 0

    #Api call for user ID
    response = requests.get("https://api.spotify.com/v1/me", headers = {'Authorization' : auth})
    response = response.json()
    userid = response['id']

    #If user chose new playlisy make api call to create playlist
    if existingstate == "New" or "new" or "N" or "n":
        params = {
        "name": playlistname,
        "description": "Playlist transfer from local",
        "public": 'false'
        }

        response = requests.request('post', "https://api.spotify.com/v1/users/"+ userid +"/playlists", headers= {'Authorization' : auth,"Content-Type": "application/json","Accept": "application/json"}, params=None ,data=json.dumps(params)) 
        response = response.json()
        playlistid= response['id']

    #Else api call to retrive existing playlists
    elif existingstate == "Existing" or "existing" or "Exists" or "exists" or "E" or "e" or "Exist" or "exist":
        response = requests.get("https://api.spotify.com/v1/me/playlists", headers = {'Authorization' : auth})
        response = response.json()
        
        while response['items'][i]['name'] != playlistname:
            if i + 1 == len(response['items']):
                print("Playlist Not Found")
                return
            i += 1

        playlistid = response['items'][i]['id']

    #Batch processing api calls for track uploafs
    current = 0
    trackbuffer = ''
    j = 0
    if listlen > 30:
        while j < len(songlist):
            if j + 1 == len(songlist):
                trackbuffer = trackbuffer + songlist[j]
                response = requests.request('post', "https://api.spotify.com/v1/playlists/"+ playlistid +"/tracks?uris=" + trackbuffer, headers= {'Authorization' : auth}) 
                trackbuffer = ''
            if songlist[j] == '%':
                if songlist[j + 1] == '2' and songlist[j + 2] == 'C':
                    current += 1
                    if current == 30:
                        response = requests.request('post', "https://api.spotify.com/v1/playlists/"+ playlistid +"/tracks?uris=" + trackbuffer, headers= {'Authorization' : auth}) 
                        trackbuffer = ''
                        current = 0
                        j = j + 3
            trackbuffer = trackbuffer + songlist[j]
            j += 1
    else:
        #Api call to add songs to playlist
        response = requests.request('post', "https://api.spotify.com/v1/playlists/"+ playlistid +"/tracks?uris=" + songlist, headers= {'Authorization' : auth}) 

    print(str(len(unsuccesful)) + " Unsuccesful tracks: "+ str(unsuccesful))
    print(str(len(untagged)) + " Untagged tracks: "+ str(untagged))

#Recursive calls to search subdirectories
def gettracks(directoryencode,store):
    for entry in os.scandir(directoryencode):
        filename = os.fsdecode(entry)
        if entry.is_file() and filename.endswith(".mp3"):
            store.append(filename)
        elif entry.is_dir():
            gettracks(entry.path,store)


#Create temp server to handle URI redirect and retrive Auth Code
def wait_for_request(server_class=http.server.HTTPServer,
                     handler_class=http.server.BaseHTTPRequestHandler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.handle_request()


def authenticate():
    old_stderr = sys.stderr
    result = StringIO()
    sys.stderr = result
    url = 'https://accounts.spotify.com/en/authorize?response_type=code&client_id=128418d86c274651af8cdc709df1c143&redirect_uri=http://localhost:8000&scope=user-read-private%20user-read-email%20playlist-modify-private%20playlist-modify-public%20playlist-read-private'
    webbrowser.open(url)
    wait_for_request()
    sys.stderr = old_stderr
    return result

def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

if __name__ == "__main__":
    main()
    input()
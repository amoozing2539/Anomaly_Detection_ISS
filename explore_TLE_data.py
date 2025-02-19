import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
import pickle
from tabulate import tabulate

from sgp4.earth_gravity import wgs84
from sgp4.api import Satrec, jday

import os
from dotenv import load_dotenv


#Credentials for API
def load_credentials(file_path):
   
    credentials = {}
    with open(file_path, 'r') as f:
        for line in f:
            key, value = line.strip().split('=')
            credentials[key] = value
    return credentials

credentials = load_credentials('config.txt')
username = credentials['username']
password = credentials['password']
login_payload = {
    'identity':username,
    'password': password
}
login_url = "https://www.space-track.org/ajaxauth/login"

def fetch_tle_data(norad_cat_id): #Call API if available
    # Construct the API request URL
    url = "https://www.space-track.org/basicspacedata/query/class/tle/NORAD_CAT_ID/25544/orderby/EPOCH%20desc/limit/10000/format/json/"

    with requests.Session() as session:
        login_response = session.post(login_url, data=login_payload)
        if login_response.status_code != 200:
            print("Login failed.")
            return None
        print("Login successful.")

        response = session.get(url)
        print(response.status_code)
        data = response.text
        print(data)

def parse_tle_set(tle_set):
    """
    Parse a single TLE set into a dictionary of orbital parameters.
    
    Parameters:
    - tle_set: List containing name, line1, line2
    
    Returns:
    - Dictionary of parsed orbital elements
    """
    name = tle_set[0].strip()
    line1 = tle_set[1]
    line2 = tle_set[2]

    # Parse epoch
    year = int(line1[18:20])
    day = float(line1[20:32])

    if year < 60:
        year += 2000
    else:
        year += 1900

    epoch = datetime(year, 1, 1) + timedelta(days=float(day) - 1)

    # Extract orbital elements
    return {
        'name': name,
        'epoch': epoch,
        'catalog_number': int(line1[2:7]),
        'inclination': float(line2[8:16]),
        'raan': float(line2[17:25]),
        'eccentricity': float('0.' + line2[26:33]),
        'arg_perigee': float(line2[34:42]),
        'mean_anomaly': float(line2[43:51]),
        'mean_motion': float(line2[52:63]),
        'line1': line1,
        'line2': line2
    }

def compute_state_vectors(tle_line1, tle_line2, epoch):
    """
    Compute position and velocity vectors for a satellite using TLE data and epoch time.
    
    Parameters:
    - tle_line1 (str): First line of the TLE.
    - tle_line2 (str): Second line of the TLE.
    - epoch (datetime): Epoch time as a datetime object.
    
    Returns:
    - dict: A dictionary containing 'position' and 'velocity' vectors.
            Example: {'position': [x, y, z], 'velocity': [vx, vy, vz]}
    """
    try:
        # Create a satellite object from the TLE lines
        satellite = Satrec.twoline2rv(tle_line1, tle_line2)
        
        # Convert the epoch time to Julian date
        jd, fr = jday(
            epoch.year,
            epoch.month,
            epoch.day,
            epoch.hour,
            epoch.minute,
            epoch.second
        )
        
        # Propagate the satellite to the epoch time
        e, position, velocity = satellite.sgp4(jd, fr)
        
        # Check for errors during propagation
        if e != 0:
            raise ValueError(f"Error propagating TLE at epoch {epoch}: Error code {e}")
        
        # Return the position and velocity vectors
        return {
            'position': position,  # [x, y, z] in km
            'velocity': velocity   # [vx, vy, vz] in km/s
        }
    
    except Exception as ex:
        print(f"Error processing TLE: {ex}")
        return {
            'position': [None, None, None],
            'velocity': [None, None, None]
        }

def add_state_vectors_to_dataframe(df):
    """
    Add position and velocity vectors to a DataFrame containing TLE data.
    
    Parameters:
    - df (pd.DataFrame): DataFrame containing TLE data with columns 'TLE_LINE1', 'TLE_LINE2', and 'EPOCH'.
    
    Returns:
    - pd.DataFrame: Updated DataFrame with additional columns for position and velocity vectors.
    """
    # Ensure the 'EPOCH' column is a datetime object
    df['EPOCH'] = pd.to_datetime(df['EPOCH'])
    
    # Initialize lists to store position and velocity vectors
    positions = []
    velocities = []
    
    for _, row in df.iterrows():
        # Compute state vectors for each row
        state_vectors = compute_state_vectors(row['TLE_LINE1'], row['TLE_LINE2'], row['EPOCH'])
        positions.append(state_vectors['position'])
        velocities.append(state_vectors['velocity'])
    
    # Add position and velocity vectors to the DataFrame
    df['position_x'], df['position_y'], df['position_z'] = zip(*positions)
    df['velocity_x'], df['velocity_y'], df['velocity_z'] = zip(*velocities)
    
    return df

def test_login(username, password): #Check if the login credentials work
    login_url = "https://www.space-track.org/ajaxauth/login"
    query_url = "https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/25544/format/tle"

    login_payload = {
        'identity': username,
        'password': password
    }

    try:
        with requests.Session() as session:
            # Log in
            login_response = session.post(login_url, data=login_payload)
            if login_response.status_code != 200:
                print("Login failed.")
                return None

            # Fetch latest TLE data
            response = session.get(query_url)
            response.raise_for_status()
            print(response.text)  # Print fetched TLE data
    except requests.exceptions.RequestException as e:
        print(f"Error during login test: {e}")

def main():
    
    # Fetch TLE data
    # norad_id = 25544  # ISS Zarya
    # tle_data = fetch_tle_data(norad_id)
    # print(tle_data)
    
    with open ('ISS_Zayra_Historic_TLE.json', 'r') as f: 
        data = json.load(f)
    
    #convert json to dataframe and then pickle for later 
    
    data_df = pd.DataFrame(data)
    data_df_state = add_state_vectors_to_dataframe(data_df)
    print(data_df_state[['EPOCH', 'position_x', 'position_y', 'position_z', 'velocity_x', 'velocity_y', 'velocity_z']].head())
    with open('data_df_states.pkl', 'wb') as f: 
        pickle.dump(data_df_state, f)
    # with open('data_df_states.pkl', 'rb') as f: 
    #     a = pickle.load(f)
    

if __name__ == "__main__":
    main()

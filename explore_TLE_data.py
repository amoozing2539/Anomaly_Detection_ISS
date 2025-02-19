import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from tabulate import tabulate

from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv

import os
from dotenv import load_dotenv

def load_credentials(file_path):
    """
    Load credentials from a configuration file.
    
    Parameters:
    - file_path: Path to the configuration file (str)
    
    Returns:
    - Dictionary containing credentials
    """
    credentials = {}
    with open(file_path, 'r') as f:
        for line in f:
            key, value = line.strip().split('=')
            credentials[key] = value
    return credentials

def get_space_track_data(username, password, norad_id, start_date, end_date):
    """
    Fetch historical TLE data from Space-Track.org.
    
    Parameters:
    - username: Space-Track username (str)
    - password: Space-Track password (str)
    - norad_id: NORAD catalog number of the satellite (int)
    - start_date: Start date for historical data (YYYY-MM-DD format, str)
    - end_date: End date for historical data (YYYY-MM-DD format, str)
    
    Returns:
    - List of TLE sets
    """
    login_url = "https://www.space-track.org/ajaxauth/login"
    query_url = (
        f"https://www.space-track.org/basicspacedata/query/"
        f"class/tle/NORAD_CAT_ID/{norad_id}/EPOCH/%3E={start_date},%3C={end_date}/format/tle"
    )

    # Login payload
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
            print("Login successful.")

            # Debugging: Print login response
            print(f"Login Response Status Code: {login_response.status_code}")

            # Debugging: Print query URL
            print(f"Fetching data from: {query_url}")

            # Fetch TLE data
            response = session.get(query_url)
            response.raise_for_status()

            # Debugging: Print response details
            print(f"Fetch Response Status Code: {response.status_code}")
            print(f"Fetch Response Content: {response.text[:500]}")  # Print first 500 chars

            # Split response into individual TLEs
            tle_data = response.text.strip().split('\n')
            tle_sets = [tle_data[i:i+3] for i in range(0, len(tle_data), 3)]

            return tle_sets

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

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

def add_state_vectors(df):
    """
    Add position and velocity vectors to the DataFrame.
    
    Parameters:
    - df: DataFrame containing TLE data
    
    Returns:
    - Updated DataFrame with state vectors
    """
    positions = []
    velocities = []

    for _, row in df.iterrows():
        satellite = twoline2rv(row['line1'], row['line2'], wgs84)
        position, velocity = satellite.propagate(
            row['epoch'].year, 
            row['epoch'].month, 
            row['epoch'].day, 
            row['epoch'].hour, 
            row['epoch'].minute, 
            row['epoch'].second
        )
        positions.append(position)
        velocities.append(velocity)

    df['position_x'], df['position_y'], df['position_z'] = zip(*positions)
    df['velocity_x'], df['velocity_y'], df['velocity_z'] = zip(*velocities)
    return df

def test_login(username, password): ###Credentials are right
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
    # Load credentials
    credentials = load_credentials('config.txt')
    username = credentials['username']
    password = credentials['password']

    # Define parameters
    norad_id = 25544  # ISS Zarya
    start_date = "2025-01-01"
    end_date = "2025-02-01"

    # Fetch TLE data
    tle_sets = get_space_track_data(username, password, norad_id, start_date, end_date)

    if not tle_sets:
        print("Failed to fetch TLE data.")
        return

    # Parse TLE data into a DataFrame
    parsed_data = [parse_tle_set(tle_set) for tle_set in tle_sets]
    df = pd.DataFrame(parsed_data)

    # Add state vectors
    df = add_state_vectors(df)

    # Preprocess the dataset
    df.drop_duplicates(subset='epoch', keep='first', inplace=True)
    df.dropna(subset=['inclination', 'eccentricity', 'mean_motion'], inplace=True)

    # Save the cleaned dataset
    output_file = 'cleaned_iss_zarya_tle_data.csv'
    df.to_csv(output_file, index=False)
    print(f"Cleaned dataset saved to '{output_file}'")

if __name__ == "__main__":
    main()

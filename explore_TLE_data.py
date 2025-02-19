import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv



def get_celestrak_data(catalog_number=None, satellite_name=None, dataset='active'): 
    """
    Fetch TLE data from Celestrak's API 
    
    Parameters: 
    - catalog_number: NORAD catalog number (int)
    - satellite_name: Name of satellite (str)
    - dataset: Predefined dataset like 'active', 'stations', 'visual', etc.
    
    Returns: List of TLE data
    """
    base_url = "https://celestrak.org/NORAD/elements/gp.php"
    
    #setup parameters
    params = {'FORMAT': 'TLE'}
    
    if catalog_number:
        params['CATNR'] = str(catalog_number)
    elif satellite_name:
        params['NAME'] = satellite_name
    else:
        # If no specific satellite, get predefined dataset
        params['GROUP'] = dataset
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Print response status and URL for debugging
        # print(f"Request URL: {response.url}")
        # print(f"Status Code: {response.status_code}")
        
        # Split response into individual TLEs (3 lines each)
        tle_data = response.text.strip().split('\n')
        
        # Print raw data length for debugging
        # print(f"Received {f(tle_data)} lines of data\n")
        
        # Group into sets of three lines
        tle_sets = [tle_data[i:i+3] for i in range(0, len(tle_data), 3)]
        
        return tle_sets
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def parse_tle(line1, line2):
    # Extract orbital elements
    epoch = line1[18:32]
    inclination = float(line2[8:16])
    raan = float(line2[17:25])
    eccentricity = float('0.' + line2[26:33])
    arg_perigee = float(line2[34:42])
    mean_anomaly = float(line2[43:51])
    mean_motion = float(line2[52:63])
    
    #Convert orbital elements to read
    
    return {
        'epoch': epoch,
        'inclination': inclination,
        'raan': raan,
        'eccentricity': eccentricity,
        'arg_perigee': arg_perigee,
        'mean_anomaly': mean_anomaly,
        'mean_motion': mean_motion
    }

def tle_to_dataframe(tle_sets):
    """
    Convert TLE sets to a pandas DataFrame with orbital parameters
    
    Parameters:
    tle_sets: List of TLE sets (each set containing name, line1, line2)
    
    Returns:
    pandas DataFrame with parsed orbital elements
    """
    data = []
    
    for tle_set in tle_sets:
        name = tle_set[0].strip()
        line1 = tle_set[1]
        line2 = tle_set[2]
        
        # Parse epoch
        year = int(line1[18:20])
        day = float(line1[20:32])
        
        # Convert two-digit year to full year
        if year < 57:  # Adjust this cutoff based on your needs
            year += 2000
        else:
            year += 1900
            
        # Convert day of year to datetime
        epoch = datetime(year, 1, 1) + timedelta(days=float(day) - 1)
        
        # Extract orbital elements
        tle_dict = {
            'name': name,
            'epoch': epoch,
            'catalog_number': int(line1[2:7]),
            'classification': line1[7:8],
            'inclination': float(line2[8:16]),
            'raan': float(line2[17:25]),
            'eccentricity': float('0.' + line2[26:33]),
            'arg_perigee': float(line2[34:42]),
            'mean_anomaly': float(line2[43:51]),
            'mean_motion': float(line2[52:63]),
            'rev_number': float(line1[63:68])
        }
        
        # Calculate additional parameters
        n = tle_dict['mean_motion'] * 2 * np.pi / 86400  # Convert to radians/sec
        a = (398600.4418 / (n * n)) ** (1/3)  # Semi-major axis in km
        
        tle_dict.update({
            'semi_major_axis': a,
            'period_minutes': 1440 / tle_dict['mean_motion'],
            'apogee': a * (1 + tle_dict['eccentricity']) - 6378.137,  # km above Earth
            'perigee': a * (1 - tle_dict['eccentricity']) - 6378.137  # km above Earth
        })
        
        data.append(tle_dict)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Set datetime index
    df.set_index('epoch', inplace=True)
    
    return df

def get_satellite_dataframe(catalog_number=None, satellite_name=None, dataset='active'):
    """
    Get satellite data as a pandas DataFrame
    """
    # Get TLE data from CelesTrak
    tle_sets = get_celestrak_data(catalog_number, satellite_name, dataset)
    
    if not tle_sets:
        return None
        
    # Convert to DataFrame
    df = tle_to_dataframe(tle_sets)
    
    return df

def add_state_vectors(df):
    """
    Add position and velocity vectors to the DataFrame
    Requires sgp4 library: pip install sgp4
    """
    positions = []
    velocities = []
    
    for idx, row in df.iterrows():
        # Create satellite object
        satellite = twoline2rv(row['line1'], row['line2'], wgs84)
        
        # Get position and velocity at epoch
        position, velocity = satellite.propagate(
            idx.year, 
            idx.month, 
            idx.day, 
            idx.hour, 
            idx.minute, 
            idx.second
        )
        
        positions.append(position)
        velocities.append(velocity)
    
    # Add as new columns
    df['position_x'], df['position_y'], df['position_z'] = zip(*positions)
    df['velocity_x'], df['velocity_y'], df['velocity_z'] = zip(*velocities)
    
    return df

def main():
    
    # iss_tles = get_celestrak_data(catalog_number=25544)#get ISS data
    # # Example of processing the data
    # if iss_tles:
    #     for tle_set in iss_tles:
    #         name = tle_set[0].strip()
    #         line1 = tle_set[1]
    #         line2 = tle_set[2]
    #         print(f"Satellite: {name}")
    #         print(f"Line 1: {line1}")
    #         print(f"Line 2: {line2}")
    iss_df = get_satellite_dataframe(catalog_number=25544)
    iss_df_state_vec = add_state_vectors(iss_df)
    
    if iss_df is not None: #iss_df is not none
        print("\nISS Orbital Parameters:")
        print(iss_df)
        
        print("\nBasic statistics:")
        print(f"Orbital Period: {iss_df['period_minutes'].iloc[0]:.2f} minutes")
        print(f"Inclination: {iss_df['inclination'].iloc[0]:.2f} degrees")
        print(f"Semi-major axis: {iss_df['semi_major_axis'].iloc[0]:.2f} km")
        
    if iss_df_state_vec is not None: 
        
    
if __name__ == "__main__":
    main()


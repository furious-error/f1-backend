from flask import Flask, jsonify, request
import fastf1 as ff1
import pandas as pd
import numpy as np
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://furious-error.github.io"}})

CACHE_DIR = 'fastf1_cache'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
ff1.Cache.enable_cache(CACHE_DIR)

def serialize_df_rows(df):
    """
    Converts a DataFrame to a list of dictionaries, handling specific types
    like Timedelta and NaT for JSON serialization.
    """
    records = []
    if df is None or df.empty:
        return records

    for _, row in df.iterrows():
        record = {}
        for col_name, value in row.items():
            if pd.isna(value):  
                record[col_name] = None
            elif isinstance(value, pd.Timedelta):
                record[col_name] = str(value)  
            elif isinstance(value, (np.datetime64, pd.Timestamp)):
                record[col_name] = value.isoformat() if pd.notna(value) else None
            elif isinstance(value, np.bool_):
                record[col_name] = bool(value)
            elif isinstance(value, (np.integer, np.floating)): 
                record[col_name] = value.item()
            else:
                record[col_name] = value
        records.append(record)
    return records

@app.route('/f1data', methods=['GET'])
def get_f1_data():
    year = request.args.get('year', type=int)
    gp = request.args.get('gp', type=str) 
    session_no = request.args.get('session', type=str)

    if not all([year, gp, session_no]):
        return jsonify({"error": "Missing parameters. Required: year, gp, session"}), 400

    try:
        session = ff1.get_session(year, gp, session_no)
        session.load()
        is_practice = "Practice" in session.name


        if is_practice:
            if session.laps is None or session.laps.empty:
                return jsonify({"error": f"No lap data available for {year} {gp} {session_no}"}), 404

            laps_df = session.laps
            output_data = []
            drivers = laps_df['Driver'].unique()

            for driver_abbr in drivers:
                driver_laps_df = laps_df[laps_df['Driver'] == driver_abbr].copy()
                
                if driver_laps_df.empty:
                    continue

                driver_number = str(driver_laps_df['DriverNumber'].iloc[0])
                team_name = driver_laps_df['Team'].iloc[0]

                driver_info = {
                    "Driver": driver_abbr,
                    "DriverNumber": driver_number,
                    "Team": team_name,
                    "Stints": []
                }

                stints = driver_laps_df['Stint'].unique()
                for stint_num in stints:
                    stint_laps_df = driver_laps_df[driver_laps_df['Stint'] == stint_num]
                    
                    stint_data = {
                        "Stint": float(stint_num),
                        "Laps": serialize_df_rows(stint_laps_df)
                    }
                    driver_info["Stints"].append(stint_data)
                output_data.append(driver_info)
            
            return jsonify(output_data)

        else: 
            if session.results is None or session.results.empty:
                 return jsonify({"error": f"No results data available for {year} {gp} {session_no}"}), 404
            
            results_data = serialize_df_rows(session.results)
            return jsonify(results_data)

    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
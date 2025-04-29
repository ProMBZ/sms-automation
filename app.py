import streamlit as st
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import json
from twilio.rest import Client
from datetime import datetime
from google.auth.transport.requests import Request

# --------- Settings ---------
APP_PASSWORD = "NextAxion_"
GOOGLE_SHEET_ID = "1UE2oVPj7VqIJJZ5MI0fvwTak7RpvA4kyN6wtbOTGgI8"  # <-- Update with correct Google Sheet ID
LOGO_PATH = "nextaxion.jpeg"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']  # Full access to the sheet
# -----------------------------

# Initialize authentication state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Load logo function
def show_logo():
    st.markdown(
        f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="data:image/jpeg;base64,{get_image_base64(LOGO_PATH)}" width="150" />
        </div>
        """,
        unsafe_allow_html=True
    )

# Function to encode logo image
def get_image_base64(image_path):
    import base64
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Login screen
if not st.session_state.authenticated:
    show_logo()
    st.markdown(
        "<h2 style='text-align: center;'>NextAxion Portal</h2>",
        unsafe_allow_html=True
    )
    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Try again.")

else:
    # After login
    show_logo()
    st.markdown("<h2 style='text-align: center;'>NextAxion Portal</h2>", unsafe_allow_html=True)
    st.title("📨 Send Offers via SMS")

    # Step 1: Authenticate and get Google Sheet data
    st.subheader("1. Authenticate with Google and fetch your Google Sheet data")
    if st.button("Authenticate with Google"):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())  # Refresh credentials
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        # Step 2: Connect to Google Sheets API and Fetch Data
        try:
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()

            # Specify the range to fetch (e.g., Sheet1)
            range_name = "Sheet1!A:C"  # Assuming columns A, B, C have Name, Phone, Sent columns
            result = sheet.values().get(spreadsheetId=GOOGLE_SHEET_ID, range=range_name).execute()
            values = result.get('values', [])

            if not values:
                st.error("❌ No data found in the sheet.")
            else:
                df = pd.DataFrame(values[1:], columns=values[0])  # Assuming first row is header
                st.subheader("2. Preview your data 📄")
                st.dataframe(df)

                # Step 3: Enter Twilio Credentials after Google Sheet Data is Loaded
                st.subheader("3. Enter Twilio Credentials")
                account_sid = st.text_input("Twilio Account SID")
                auth_token = st.text_input("Twilio Auth Token", type="password")
                twilio_phone_number = st.text_input("Twilio Phone Number (example: +1234567890)")

                # Ensure all Twilio credentials are entered
                if account_sid and auth_token and twilio_phone_number:
                    # Step 4: Send Messages button
                    if st.button("🚀 Send Messages"):
                        twilio_client = Client(account_sid, auth_token)

                        logs = []

                        # Loop over the contacts in the Google Sheet
                        for index, row in df.iterrows():
                            name = row.get('Name')
                            phone = row.get('Phone')
                            sent_status = row.get('Sent')

                            if pd.isna(name) or pd.isna(phone) or sent_status == "Yes":
                                continue  # Skip if no name/phone or already sent

                            message = f"Hello {name}, we are currently running a new offer. Do you want to book an appointment?"

                            try:
                                # Send the SMS using Twilio
                                twilio_client.messages.create(
                                    body=message,
                                    from_=twilio_phone_number,
                                    to=phone
                                )

                                # Update status to 'Yes' if the message is sent
                                update_range = f"Sheet1!C{index + 2}"  # Update "Sent" column (C) in the row
                                body = {
                                    'values': [['Yes']]
                                }
                                sheet.values().update(spreadsheetId=GOOGLE_SHEET_ID, range=update_range, valueInputOption="RAW", body=body).execute()

                                logs.append({
                                    "Name": name,
                                    "Phone": phone,
                                    "Status": "✅ Sent",
                                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                })
                            except Exception as e:
                                logs.append({
                                    "Name": name,
                                    "Phone": phone,
                                    "Status": f"❌ Failed: {e}",
                                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                })

                        # Save logs to CSV
                        logs_df = pd.DataFrame(logs)
                        logs_file = "logs.csv"
                        logs_df.to_csv(logs_file, index=False)

                        st.success("✅ All messages processed!")
                        st.download_button(
                            label="📥 Download Logs",
                            data=logs_df.to_csv(index=False),
                            file_name="sms_logs.csv",
                            mime="text/csv"
                        )
                else:
                    st.info("Please fill in all Twilio credentials to proceed.")
        except Exception as e:
            st.error(f"Error fetching Google Sheet data: {e}")
    else:
        st.info("Please authenticate to proceed.")

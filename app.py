import streamlit as st
import pandas as pd
import json
import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import os
from io import BytesIO
import sqlite3

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel('gemini-pro')


def get_gemini_response(input,prompt):
    response = model.generate_content([input,prompt])
    return response.text


def df_to_sqlite(df, db_name):
    conn = sqlite3.connect(f'{db_name}.db')
    df.to_sql(db_name, conn, index=False, if_exists='replace')
    conn.commit()
    conn.close()

    output = BytesIO()
    with open(f'{db_name}.db', 'rb') as f:
        output.write(f.read())
    output.seek(0)
    return output

def process_file(uploaded_file):
    if uploaded_file is not None:
        if uploaded_file.name.endswith('.json'):
            data = json.load(uploaded_file)
            df = pd.json_normalize(data)
        elif uploaded_file.name.endswith('.xlsx') or uploaded_file.name.endswith('.xls'):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            st.error("Unsupported file type. Please upload a JSON or Excel file.")
            return None
        return df
    else:
        raise FileNotFoundError("No file Uploded!")

def read_sql_query(sql,db):
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(sql)
    data = cursor.fetchall()
    conn.commit()
    conn.close()
    for row in data:
        print(row)
    return data




## Frontend Part:

st.set_page_config(page_title="Text to SQL", layout="wide")



if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'df' not in st.session_state:
    st.session_state['df'] = None

if 'name' not in st.session_state:
    st.session_state['name'] = ''

st.title("Text to SQL Query Web App")


col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.header("Upload Data")
    uploaded_file = st.file_uploader("Choose a JSON or Excel or CSV file", type=['json', 'xlsx', 'xls','csv'])
    st.session_state['name'] = st.text_input("Table name - ")
    if st.button("Submit"):
        with st.spinner("Processing..."):
            df = process_file(uploaded_file)
            st.session_state['df'] = df
            if st.session_state['df'] is not None:
                st.success("File uploaded and processed successfully!")
    
    if st.session_state['df'] is not None:
        st.write("## DataFrame Preview")
        st.dataframe(st.session_state['df'])

        if st.button("Convert to SQLite Database"):
            db_file = df_to_sqlite(st.session_state['df'], st.session_state['name'])
            st.download_button(label="Download SQLite Database", data=db_file, file_name="data.db")

with col2:
    st.header("Enter Your SQL Query")
    query = st.text_input("Enter your query here")
    if st.button("Run Query", key="run_query"):
        if query:
            q_time = datetime.datetime.now()
            name = st.session_state['name']
            columns = list(st.session_state['df'].columns)
            st.session_state['chat_history'].append(("You",query,q_time.strftime("%d-%m-%Y %H:%M")))
            prompt = f"""
            You are an expert in converting English questions to SQL query! For example 
            if the SQL database has the name Students and has the following columns - name, class, address, roll, phone_number \n\nFor example,\nExample 1 - How many entries of records are present?, 
            the SQL command will be something like this SELECT COUNT(*) FROM Students ;
            \nExample 2 - Tell me all the students studying in 10A class?, 
            the SQL command will be something like this SELECT * FROM Students 
            where CLASS="10A";
            Here the user will give you the table name and also the column name in a list form you have to extract 
            the table name and column name from the list.
            The table name is {name} & columns are {columns} 
            also the sql code should not have ``` in beginning or end and sql word in output.

            """
            # print(prompt)
            sql_response = get_gemini_response(query,prompt)
            print(sql_response)
            response = read_sql_query(sql_response,f'{name}.db')
            st.success("Query executed successfully!")
            r_time = datetime.datetime.now()
            st.session_state['chat_history'].append(("Bot",response,r_time.strftime("%d-%m-%Y %H:%M")))
            st.write(f"SQl query: {sql_response}\n")
            st.write("The solution: ")
            for num,row in enumerate(response):
                # print(type(row))
                new = tuple(map(str, row))
                answer = " ".join(new)
                st.write(f"{num+1}. {answer}")


with col3:
    st.header("Chat History")
    chat_history_container = st.container()
    with chat_history_container:
        st.write("Previous SQL Queries")
        # Add a scrollable chat history box
        chat_history_expander = st.expander("Chat History", expanded=True)
        with chat_history_expander:
            chat_history = st.session_state['chat_history']
            for role,chat,time in chat_history:
                st.write(f"{role} : {chat} ({time})")
    if st.button("Clear History"):
        st.session_state['chat_history'] = []
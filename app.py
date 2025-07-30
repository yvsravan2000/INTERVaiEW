# Import packages and modules | External
import os
import time
import json
import requests
import pandas as pd
import streamlit as st
import snowflake.connector as sf

# Page configuration
with st.spinner(text="Loading...", show_time=True):
    # Configure the page
    st.set_page_config(
        page_title="IntervAIew",
        page_icon=":material/group_work:",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={
            "Get Help": f"mailto:yvsravan2000@gmail.com"
        }
    )

    # Initialize the session state
    if 'init' not in st.session_state:
        st.session_state.init = True
        st.session_state.logged_in = False
        st.session_state.cortex_chat_history = {'user_input': [], 'assistant_response': [], 'response_time_in_seconds': [], 'total_tokens': []}
        st.session_state.cortex_chat_settings = {'enable_guardrails': False, 'enable_conversation_memory': True, 'system_prompt_content': st.secrets["intervaiew"]["system_prompt_content"]}
        st.session_state.remaining_balance_in_usd = 0.0
        st.session_state.sf_connection = None
        st.session_state.sf_cursor = None

############################### Page functions ###############################
# Function to establish a Snowflake connection
def create_connection() -> None:
    """
    Establish a connection to Snowflake using credentials from the secret module and the password from Streamlit session state.
    Sets the connection and cursor in the session state for later use.

    Returns:
        None
    """
    try:
        sf_connection = sf.connect(
            user=st.secrets["snowflake"]["username"],
            account=st.secrets["snowflake"]["account"],
            password=st.secrets["snowflake"]["password"],
            warehouse=st.secrets["snowflake"]["warehouse"],
            database=st.secrets["snowflake"]["database"],
            schema=st.secrets["snowflake"]["schema"]
        )

        st.session_state.sf_connection = sf_connection
        st.session_state.sf_cursor = sf_connection.cursor()

    except Exception as error:
        st.session_state.sf_connection = None
        st.session_state.sf_cursor = None

# Function to execute a Snowflake query and return the r0,c0 from the result
def execute_query_and_return_first_value(query: str) -> str:
    """
    Execute a Snowflake query and return the first value from the result.

    Args:
        query (str): The SQL query to execute.

    Returns:
        str: The first value from the result set, or None if no results.
    """
    if st.session_state.sf_connection is None:
        create_connection()

    try:
        st.session_state.sf_cursor.execute(query)
        result = st.session_state.sf_cursor.fetchone()
        return result[0] if result else None
    except Exception as error:
        return None

# Function to convert USD to INR
st.cache_data(ttl=3600)
def convert_usd_to_inr(usd_amount: float) -> float:
    response = requests.get(st.secrets["freecurrencyapi"]["usd2inr_api_url"])
    data = response.json()
    usd_to_inr_rate = float(data.get("data", {}).get("INR", 85.4))  # Default to 85.4 if not found
    return usd_amount * usd_to_inr_rate

# Function to generate response
def generate_response(input_tokens: str) -> tuple:
    """
    Generate response for the given input tokens.
    
    Args:
        input_tokens (str): The input tokens from the user.
        
    Returns:
        tuple: A tuple containing the response tokens and total tokens count.
    """
    
    # Prepare the input tokens for the query
    input_tokens = input_tokens.replace("'", "''").replace('"', '""')  # Escape double quotes for SQL query

    if(st.session_state.cortex_chat_settings['enable_conversation_memory']):
        history_tokens = ""
        # If conversation memory is enabled, include previous messages in the input
        for iterator in range(len(st.session_state.cortex_chat_history['user_input'])):
            user_input = st.session_state.cortex_chat_history['user_input'][iterator].replace("'", "''").replace('"', '""')
            assistant_response = st.session_state.cortex_chat_history['assistant_response'][iterator].replace("'", "''").replace('"', '""')
            history_tokens += f",\n OBJECT_CONSTRUCT('role', 'user', 'content', '{user_input}'),\n OBJECT_CONSTRUCT('role', 'assistant', 'content', '{assistant_response}')"

        response_tokens = json.loads(execute_query_and_return_first_value(f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'openai-gpt-4.1',
            ARRAY_CONSTRUCT(
                OBJECT_CONSTRUCT('role', 'system', 'content', '{st.session_state.cortex_chat_settings['system_prompt_content']}'){history_tokens},
                OBJECT_CONSTRUCT('role', 'user', 'content', '{input_tokens}')
            ),
            OBJECT_CONSTRUCT(
                'guardrails', {'FALSE' if not st.session_state.cortex_chat_settings['enable_guardrails'] else 'TRUE'}
            )
        ) AS RESPONSE;
        """))

        return str(response_tokens['choices'][0]['messages']), int(response_tokens['usage']['total_tokens'])
    else:
        response_tokens = json.loads(execute_query_and_return_first_value(f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'openai-gpt-4.1',
            ARRAY_CONSTRUCT(
                OBJECT_CONSTRUCT('role', 'system', 'content', '{st.session_state.cortex_chat_settings['system_prompt_content']}'),
                OBJECT_CONSTRUCT('role', 'user', 'content', '{input_tokens}')
            ),
            OBJECT_CONSTRUCT(
                'guardrails', {'FALSE' if not st.session_state.cortex_chat_settings['enable_guardrails'] else 'TRUE'}
            )
        ) AS RESPONSE;
        """))

        return str(response_tokens['choices'][0]['messages']), int(response_tokens['usage']['total_tokens'])

# Function to clear chat history
@st.dialog(title="Clear Chat History", width="small")
def clear_chat_history():
    """
    Clear the chat history.
    """
    st.write("Are you sure you want to clear the chat history? This action cannot be undone.")
    if(st.button(label="Yes", type="primary", icon=":material/mop:", use_container_width=True)):
        st.session_state.cortex_chat_history = {'user_input': [], 'assistant_response': [], 'response_time_in_seconds': [], 'total_tokens': []}
        st.rerun()  # Rerun the app to reflect changes immediately

# Function to modify chat settings
@st.dialog(title="Chat Settings", width="small")
def modify_chat_settings():
    """
    Modify chat settings.
    """
    st.write("You can modify the chat settings below:")
    
    # Enable guardrails
    enable_guardrails = st.checkbox(label="Enable Guardrails", value=st.session_state.cortex_chat_settings['enable_guardrails'])
    
    # Enable conversation memory
    enable_conversation_memory = st.checkbox(label="Enable Conversation Memory", value=st.session_state.cortex_chat_settings['enable_conversation_memory'])
    
    if(st.button(label="Update", type="primary", icon=":material/check:", use_container_width=True)):
        st.session_state.cortex_chat_settings['enable_guardrails'] = enable_guardrails
        st.session_state.cortex_chat_settings['enable_conversation_memory'] = enable_conversation_memory
        st.toast(":gray[**Chat settings updated successfully!**]", icon=":material/notifications_active:")
        time.sleep(2)  # Wait for a couple of seconds to show the toast message
        if(not(st.session_state.cortex_chat_settings['enable_conversation_memory'])):
            # Clear chat history if conversation memory is disabled
            st.session_state.cortex_chat_history = {'user_input': [], 'assistant_response': [], 'response_time_in_seconds': [], 'total_tokens': []}
        st.rerun()  # Rerun the app to reflect changes immediately

# Function to save chat history
@st.dialog(title="Save Conversation", width="small")
def save_chat_history():
    """
    Save the current conversation.
    """
    cortex_conversation_file_name = st.text_input("Enter a file name to save the conversation (e.g., chat_history)")

    if(st.button(label="Save", type="primary", icon=":material/save:", use_container_width=True)):
        # Prepare the file path
        save_folder = os.path.join("chats")
        os.makedirs(save_folder, exist_ok=True)
        file_path = os.path.join(save_folder, f"{cortex_conversation_file_name}.json") if cortex_conversation_file_name else ""

        # Save/Overwrite the chat history to a JSON file
        if file_path:
            with open(file_path, "w") as f:
                json.dump(st.session_state.cortex_chat_history, f)
            st.toast(":gray[**Conversation saved successfully!**]", icon=":material/notifications_active:")
            time.sleep(2)  # Wait for a couple of seconds to show the toast message
            st.rerun()  # Rerun the app to reflect changes immediately

# Function to delete chat history
@st.dialog(title="Delete Conversation", width="small")
def delete_chat_history(file_path: str):
    """
    Delete the chat history.
    """
    st.write("Are you sure you want to delete the conversation? This action cannot be undone.")
    if(st.button(label="Yes", type="primary", icon=":material/delete:", use_container_width=True)):
        os.remove(file_path)
        st.toast(":gray[**Conversation deleted successfully!**]", icon=":material/notifications_active:")
        time.sleep(2)  # Wait for a couple of seconds to show the toast message
        st.rerun()  # Rerun the app to reflect changes immediately

############################### Page contents ###############################
# Title
st.title(":primary-background[ :primary[:material/group_work:] INTERV:primary[ai]EW]")

# Create Snowflake connection if not already created
if(st.session_state.sf_connection is None):
    with st.spinner(text="Creating Snowflake connection...", show_time=True):
        create_connection()
        remaining_balance_in_usd = execute_query_and_return_first_value("SELECT MAX_BY(FREE_USAGE_BALANCE, DATE) AS REMAINING_CREDITS FROM SNOWFLAKE.ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY;")
        st.session_state.remaining_balance_in_usd = float(remaining_balance_in_usd if remaining_balance_in_usd is not None else 400.0)

# Page tabs
ai_page1_tab1, ai_page1_tab2 = st.tabs([":material/asterisk: Chat Interface", ":material/chat: Saved Conversations"])

with ai_page1_tab1:
    # Tab1 columns
    ai_page1_tab1_col1, ai_page1_tab1_col2 = st.columns(spec=[27, 72], gap="small", vertical_alignment="top")

    # Column 1: Stats
    with ai_page1_tab1_col1:
        # Calculate stats
        ai_page1_tab1_stats_df = pd.DataFrame(st.session_state.cortex_chat_history)
        total_tokens_sum = ai_page1_tab1_stats_df['total_tokens'].sum()
        longest_response_time = ai_page1_tab1_stats_df['response_time_in_seconds'].max()
        response_time_average = ai_page1_tab1_stats_df['response_time_in_seconds'].mean()
        snowflake_credits_spent = ((1.4/1000000)*total_tokens_sum)+((1/3600)*ai_page1_tab1_stats_df['response_time_in_seconds'].sum())
        equivalent_cost_inr = snowflake_credits_spent * (convert_usd_to_inr(4))

        # Display stats
        remaining_balance = ((convert_usd_to_inr(1)) * st.session_state.remaining_balance_in_usd) / 1000
        if(len(st.session_state.cortex_chat_history['user_input']) == 0):
            st.markdown(f"## :primary[<u>Stats</u>] \n#### :grey[*Remaining Balance*]<br>[₹{remaining_balance:.1f}k] \n#### :grey[*Conversation Cost*]<br>[₹0.00] \n#### :grey[*Longest Response Time*]<br>[n/a] \n#### :grey[*Avg. Response Time*]<br>[n/a] \n#### :grey[*Total Tokens*]<br>[0]", unsafe_allow_html=True)
        else:
            st.markdown(f"## :primary[<u>Stats</u>] \n#### :grey[*Remaining Balance*]<br>[₹{remaining_balance:.1f}k] \n#### :grey[*Conversation Cost*]<br>[₹{equivalent_cost_inr:.2f}] \n#### :grey[*Longest Response Time*]<br>[{longest_response_time:.2f} seconds] \n#### :grey[*Avg. Response Time*]<br>[{response_time_average:.2f} seconds] \n#### :grey[*Total Tokens*]<br>[{total_tokens_sum:,}]", unsafe_allow_html=True)

    # Column 2: Chat Interface
    with ai_page1_tab1_col2:
        # Chat history container
        with st.container(height=440, border=True):
            for iterator in range(len(st.session_state.cortex_chat_history['user_input'])):
                input_tokens = st.session_state.cortex_chat_history['user_input'][iterator]
                response_tokens = st.session_state.cortex_chat_history['assistant_response'][iterator]
                response_time_in_seconds = st.session_state.cortex_chat_history['response_time_in_seconds'][iterator]
                tokens_count = st.session_state.cortex_chat_history['total_tokens'][iterator]

                # Display user input
                with st.chat_message(name="user", avatar=":material/person:"):
                    st.markdown(input_tokens)

                # Display assistant response
                with st.chat_message(name="assistant", avatar=":material/asterisk:"):
                    st.markdown(response_tokens)

                # Display response time and tokens count
                # st.caption(f":material/acute: Response Time: {response_time_in_seconds} seconds")

            # Placeholders for new messages
            user_input_placeholder = st.empty()
            assistant_response_placeholder = st.empty()

        # Tab1 input columns
        ai_page1_tab1_col1_input_col1, ai_page1_tab1_col1_input_col2, ai_page1_tab1_col1_input_col3, ai_page1_tab1_col1_input_col4 = st.columns(spec=[82, 6, 6, 6], gap="small", vertical_alignment="center")

        # Chat input
        if(cortex_input_tokens := ai_page1_tab1_col1_input_col1.chat_input(placeholder="Ask anything", accept_file=False)):
            # Display user input in chat message container
            with user_input_placeholder.chat_message(name="user", avatar=":material/person:"):
                st.markdown(cortex_input_tokens)

            # Display assistant response in chat message container
            with assistant_response_placeholder.chat_message(name="assistant", avatar=":material/asterisk:"):
                # Generate response
                start_time = time.time()
                with st.spinner(text="Generating response...", show_time=True):
                    cortex_response_tokens, total_tokens = generate_response(cortex_input_tokens)
                end_time = time.time()
                response_time_in_seconds = int(end_time - start_time)

                assistant_response_run = st.empty()
                complete_response_tokens = ""
                assistant_response = cortex_response_tokens

                # Simulate stream of response with milliseconds delay
                for chunk in assistant_response:
                    complete_response_tokens += chunk
                    # time.sleep(1e-321)
                    # time.sleep(0.003)  # Simulate a delay for each token to mimic streaming response
                    # Add a blinking cursor to simulate typing
                    assistant_response_run.markdown(complete_response_tokens + "▌")
                assistant_response_run.markdown(complete_response_tokens)
            
                # Display response time and tokens count
                st.caption(f":material/acute: Response Time: {response_time_in_seconds} second(s)")

            st.session_state.cortex_chat_history['user_input'].append(cortex_input_tokens)
            st.session_state.cortex_chat_history['assistant_response'].append(cortex_response_tokens)
            st.session_state.cortex_chat_history['response_time_in_seconds'].append(response_time_in_seconds)
            st.session_state.cortex_chat_history['total_tokens'].append(total_tokens)

        # Chat options
        if(ai_page1_tab1_col1_input_col2.button(label=":red[**:material/mop:**]", help="Clear chat history", use_container_width=True)):
            if(len(st.session_state.cortex_chat_history['user_input']) == 0):
                st.toast(":gray[**There are no messages in the chat history to clear.**]", icon=":material/notifications_active:")
            else:
                clear_chat_history()

        if(ai_page1_tab1_col1_input_col3.button(label=":green[**:material/save:**]", help="Save chat history", use_container_width=True)):
            if(len(st.session_state.cortex_chat_history['user_input']) == 0):
                st.toast(":gray[**There are no messages in the chat history to save.**]", icon=":material/notifications_active:")
            else:
                save_chat_history()

        if(ai_page1_tab1_col1_input_col4.button(label=":blue[**:material/settings:**]", help="Chat Settings", use_container_width=True)):
            modify_chat_settings()

with ai_page1_tab2:
    # User input for saved chats
    conv_files_list = [conv_file.replace('.json', '') for conv_file in os.listdir(os.path.join("chats")) if conv_file.endswith('.json')]
    if(len(conv_files_list) == 0):
        st.info("No saved conversations found. Please save a conversation to view it here.", icon=":material/info:")
    else:
        with st.container(border=True):
            cortex_saved_chats_file_name = st.selectbox("Choose a saved conversation", options=conv_files_list, index=0, help="Select a saved " \
            "chat file to load its content.")
            ai_page1_tab2_col1, ai_page1_tab2_col2, ai_page1_tab2_col3 = st.columns(spec=[2, 2, 4], gap="medium", vertical_alignment="center", border=False)

        if(ai_page1_tab2_col1.button(label="View Conversation", type="primary", use_container_width=True, icon=":material/visibility:")):
            with st.spinner(text="Loading saved chat...", show_time=True):
                with open(os.path.join("chats", f"{cortex_saved_chats_file_name}.json"), "r") as conv_file:
                    # Load the saved chat history from the JSON file
                    saved_chat = json.load(conv_file)

                    # Display the saved chat history using chat_message
                    for iterator in range(len(saved_chat['user_input'])):
                        input_tokens = saved_chat['user_input'][iterator]
                        response_tokens = saved_chat['assistant_response'][iterator]
                        response_time_in_seconds = saved_chat['response_time_in_seconds'][iterator]
                        tokens_count = saved_chat['total_tokens'][iterator]

                        # Display user input
                        with st.chat_message(name="user", avatar=":material/person:"):
                            st.markdown(input_tokens)

                        # Display assistant response
                        with st.chat_message(name="assistant", avatar=":material/asterisk:"):
                            st.markdown(response_tokens)

        if(ai_page1_tab2_col2.button(label="**Delete Conversation**", type="secondary", use_container_width=True, icon=":material/delete:")):
            delete_chat_history(os.path.join("chats", f"{cortex_saved_chats_file_name}.json"))

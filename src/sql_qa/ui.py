from langchain_core.messages import HumanMessage
import streamlit as st
from shared.logger import get_logger

from sql_qa.chat import gen_agent_executor

logger = get_logger(__name__, log_file="./logs/")

from shared.db import get_db


st.title("Simple chat")
st.sidebar.info("This is a sidebar.")

# Initialize username in session state if not exists
if "username" not in st.session_state:
    st.session_state.username = None


def run():
    username = st.session_state.username

    if "agent_executor" not in st.session_state:
        mdb = get_db()
        agent_executor, checkpointer = next(gen_agent_executor(mdb))
        st.session_state.agent_executor = agent_executor
        st.session_state.checkpointer = checkpointer

    agent_executor = st.session_state.agent_executor
    checkpointer = st.session_state.checkpointer

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Xin chào, tôi có thể giúp gì cho bạn?"):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            configurable = {"configurable": {"thread_id": "1", "user_id": username}}
            try:
                logger.info(f"Prompt: {prompt}")
                response = agent_executor.invoke(
                    {"messages": st.session_state.messages[-10:]},
                    config=configurable,
                )
                logger.info(f"Response: {response}")
                ai_message = response["messages"][-1]
                st.markdown(ai_message.content)
                # Add assistant response to chat history
                st.session_state.messages.append(
                    {"role": "assistant", "content": ai_message.content}
                )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                logger.error(f"An error occurred: {str(e)}")
                # If there's an error, we should reinitialize the agent and checkpointer
                # del st.session_state.agent_executor
                # del st.session_state.checkpointer
                st.rerun()


# Username input section
if st.session_state.username is None:
    username = st.text_input("Please enter your username to start chatting:")
    if username:
        st.session_state.username = username
        st.rerun()
else:
    st.write(f"Welcome, {st.session_state.username}!")
    run()

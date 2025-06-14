import asyncio
import streamlit as st
from shared.logger import get_logger

from orchestrator import get_orchestrator_executor
from sql_qa.utils.invocation import ainvoke_agent

logger = get_logger("ui", log_file="./logs/")

# Initialize the event loop
if "loop" not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

st.title("Simple chat")
st.sidebar.info("This is a sidebar.")

# Initialize username in session state if not exists
if "username" not in st.session_state:
    st.session_state.username = None


async def run():
    username = st.session_state.username

    if "agent_executor" not in st.session_state:
        agent_executor = await get_orchestrator_executor()
        st.session_state.agent_executor = agent_executor

    configurable = {"configurable": {"thread_id": "1", "user_id": username}}
    agent_executor = st.session_state.agent_executor

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
            try:
                logger.info(f"Prompt: {prompt}")
                response = await ainvoke_agent(
                    agent_executor,
                    {"messages": st.session_state.messages[-20:]},
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
    try:
        st.session_state.loop.run_until_complete(run())
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
        st.error("An error occurred while processing your request. Please try again.")

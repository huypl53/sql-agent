import logging
from shared import db as mdb
from shared.logger import get_logger
import pathlib
import os
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
import getpass
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
import click


load_dotenv()

if not os.environ.get("MISTRAL_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = getpass.getpass("Enter API key for Mistral AI: ")

llm_providers = [("gpt-4o-mini", "openai"), ("mistral-large-latest", "mistralai")]


@click.group()
def cli():
    pass


@click.option(
    "--verbose", default=True, type=bool, help="To show the agent thoughts or not"
)
@cli.command()
def main(verbose) -> None:
    # Create log directory if it doesn't exist
    logger = get_logger("main", logging.INFO, log_file="./logs/")
    logger.info(f"Working directory: {os.getcwd()}")

    llm_provider = llm_providers[0]
    logger.info("LLM: {}".format(llm_provider))
    # llm = init_chat_model("mistral-large-latest", model_provider="mistralai")
    llm = init_chat_model(llm_provider[0], model_provider=llm_provider[1])
    db = mdb.db
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()
    prompt_template = """
    Bạn là một tác nhân được thiết kế để tương tác với cơ sở dữ liệu SQL.  
    Khi nhận được một câu hỏi đầu vào, hãy tạo một truy vấn {dialect} có cú pháp chính xác để chạy, sau đó xem kết quả của truy vấn và trả về câu trả lời.  
    Trừ khi người dùng chỉ định rõ số lượng mẫu họ muốn lấy, luôn giới hạn truy vấn của bạn tối đa {top_k} kết quả.  
    Bạn có thể sắp xếp kết quả theo một cột phù hợp để trả về những mẫu thú vị nhất trong cơ sở dữ liệu.  
    Không bao giờ truy vấn tất cả các cột từ một bảng cụ thể, chỉ yêu cầu các cột liên quan đến câu hỏi.  
    Bạn có quyền truy cập vào các công cụ để tương tác với cơ sở dữ liệu.  
    Chỉ sử dụng các công cụ dưới đây. Chỉ sử dụng thông tin được trả về bởi các công cụ dưới đây để xây dựng câu trả lời cuối cùng.  
    Bạn PHẢI kiểm tra kỹ truy vấn của mình trước khi thực thi. Nếu gặp lỗi khi thực thi truy vấn, hãy viết lại truy vấn và thử lại.  
    KHÔNG ĐƯỢC thực hiện bất kỳ câu lệnh DML (INSERT, UPDATE, DELETE, DROP, v.v.) nào trên cơ sở dữ liệu.  
    Để bắt đầu, bạn LUÔN PHẢI xem các bảng trong cơ sở dữ liệu để biết mình có thể truy vấn những gì.  
    KHÔNG ĐƯỢC bỏ qua bước này.  
    Sau đó, bạn nên truy vấn lược đồ của các bảng có liên quan nhất."""
    system_message = prompt_template.format(dialect="mysql", top_k=3)
    agent_executor = create_react_agent(llm, tools, prompt=system_message)

    logger.info("Starting SQL QA session")
    while (msg := input("-" * 20 + "Input `q` or `quit` to quit\nUser: ")) not in [
        "q",
        "quit",
    ]:
        # Log user input
        logger.info(f"User: {msg}")

        # Process agent response
        final_response = None
        for step in agent_executor.stream(
            {"messages": [HumanMessage(content=msg)]},
            stream_mode="values",
        ):
            if verbose:
                step["messages"][-1].pretty_print()
                # Log intermediate thoughts if verbose
                logger.info(f"Agent thought: {step['messages'][-1]}")
            final_response = step["messages"][-1]

        # Log final response
        logger.info(f"Bot: {final_response}")
        print(f"\nBot: {final_response.content}")


if __name__ == "__main__":
    main()

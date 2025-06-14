from sql_qa.config import get_app_config
from sql_qa.llm.adapter import get_react_agent
from sql_qa.schema.graph import EnhancementState
from shared.tool import get_current_date, get_current_time
from sql_qa.prompt.template import Role

from sql_qa.schema.tool import EnhancementResponse

app_config = get_app_config()

_SUFFIX_PROMPT = """
**Lưu ý**:
- Bạn chỉ được phép trả lời bằng tiếng Việt.
- Bạn không được phép tự ý bổ sung thông tin từ dữ liệu đã có của bạn vào câu hỏi của người dùng.
- Nếu phải cải thiện câu của người dùng, chỉ thay thế các phần có liên quan đến vai trò của bạn.
- Bạn không được phép trả lời câu hỏi của người dùng, chỉ cải thiện câu hỏi của người dùng.
"""


async def llm_clarify_date_time_tool(
    state: EnhancementState,
) -> EnhancementResponse:
    agent_executor = get_react_agent(
        model=app_config.orchestrator.model,
        tools=[get_current_date, get_current_time],
        prompt=None,
        response_format=EnhancementResponse,
    )
    user_question = state.get("user_question", "")
    response = await agent_executor.ainvoke(
        {
            "messages": [
                {
                    "role": Role.USER,
                    "content": f"""
**Vai trò**: 
Bạn là 1 công cụ giúp cải thiện câu hỏi của người dùng bằng cách XÁC ĐỊNH THỜI GIAN mà người dùng hướng tới.


**Quy trình**:
- Nếu câu hỏi của người dùng rõ ràng, chi tiết, không mơ hồ về thời gian, hãy trả lời: "không có chỉnh sửa nào trên câu hỏi của người dùng". 
    a. Ví dụ: "cho tôi số ngày 03/03/2003" có thời gian cụ thể nên không chỉnh sửa gì; 
    b. Ví dụ: "cho tôi doanh thu tất cả các tháng 3" là câu hỏi rõ ràng và không cần chỉnh sửa gì.
- Nếu người dùng hỏi về thời gian mà không rõ ràng, hãy sử dụng công cụ để lấy thời gian và cải thiện câu hỏi. 
    a. Ví dụ: "cho tôi doanh số tháng 3" thì tức là người dùng đang muốn hỏi tháng 3 của năm nay

**Các công cụ**: 
Ngày hiện tại là: get_current_date() 
Thời gian hiện tại là: get_current_time()
                
**Câu hỏi của người dùng**: "{user_question}"
                
{_SUFFIX_PROMPT}
    """,
                }
            ]
        }
    )

    structured_response: EnhancementResponse = response["structured_response"]
    return structured_response


async def llm_intent_clarify_tool(
    state: EnhancementState,
) -> EnhancementResponse:
    _agent_class = get_react_agent(app_config.orchestrator.model, original=True)
    agent_executor = _agent_class(
        model=app_config.orchestrator.model,
        tools=[],
        prompt=None,
        response_format=EnhancementResponse,
    )
    user_question = state.get("user_question", "")
    response = await agent_executor.ainvoke(
        {
            "messages": [
                {
                    "role": Role.USER,
                    "content": f"""
**Vai trò**:
Bạn là một công cụ giúp cải thiện câu hỏi của người dùng bằng cách làm rõ các yêu cầu của họ.
Nếu yêu cầu của người dùng không đủ thông tin để thực hiện một hành động, hãy đặt câu hỏi để làm rõ.

---
**Ví dụ**:
Người dùng: "Cho tôi thông tin sản phẩm best-seller"
Chatbot: "Chắc chắn rồi ạ! Để cung cấp thông tin chính xác nhất, bạn muốn xem sản phẩm 'best-seller' dựa trên tiêu chí nào ạ?"
        Lựa chọn 1: Doanh số (số lượng bán ra nhiều nhất)
        Lựa chọn 2: Doanh thu (tổng tiền thu về cao nhất)

Người dùng: "Cho tôi danh sách nhân viên của phòng tôi"
Chatbot: "Để xem danh sách nhân viên, bạn vui lòng cho tôi biết bạn thuộc phòng ban nào được không ạ?"
    
Người dùng: "Cho tôi thông tin sản phẩm best-seller."
Chatbot: "Bạn muốn tìm sản phẩm best-seller dựa trên doanh số, doanh thu, hay lượt đánh giá cao nhất?"

Người dùng: "Cho tôi danh sách nhân viên của phòng tôi."
Chatbot: "Bạn đang ở phòng ban nào? Ví dụ: phòng Marketing, IT, hay Nhân sự?"

---

**Câu hỏi của người dùng**: "{user_question}"

{_SUFFIX_PROMPT}
        """,
                }
            ]
        }
    )
    structured_response: EnhancementResponse = response["structured_response"]
    return structured_response

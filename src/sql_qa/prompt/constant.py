from sql_qa.prompt.template import PromptTemplate, Role, TemplateMetadata
from sql_qa.config import get_config

app_config = get_config()


class PromptConstant:
    _gen_prefix = """
    **CHÚ Ý**: 
    - Phải tuân thủ đúng cú pháp của câu lệnh SQL và các quy tắc của {dialect}.
    - Câu truy vấn SQL phải chứa thông tin có ý nghĩa
    
    """.format(
        dialect=app_config.database.dialect.upper()
    )
    system_prompt: PromptTemplate = PromptTemplate(
        template="""
Là một quản trị viên cơ sở dữ liệu chuyên nghiệp và giàu kinh nghiệm, nhiệm vụ của bạn là phân tích câu hỏi của người dùng và lược đồ cơ sở dữ liệu {dialect} để cung cấp thông tin liên quan. Bạn được cung cấp `Câu hỏi` của người dùng và `Lược đồ DB` chứa cấu trúc cơ sở dữ liệu.
        """,
        role=Role.SYSTEM,
        metadata=TemplateMetadata(
            version="1.0",
            author="msc-sql",
            tags=["system_prompt"],
        ),
    )
    table_linking_prompt: PromptTemplate = PromptTemplate(
        template="""
Hãy suy nghĩ từng bước. Xác định và liệt kê tất cả các tên bảng liên quan từ lược đồ DB dựa trên câu hỏi của người dùng và lược đồ cơ sở dữ liệu được cung cấp. Hãy đảm bảo bạn bao gồm tất cả các bảng liên quan.

**Câu hỏi SQL**: {question}

**Lược đồ DB**: {schema}

**Kết quả**:
- Trả về danh sách tên các bảng liên quan được phân cách bằng dấu phẩy theo định dạng: "bảng1, bảng2, bảng3"
        """,
        role=Role.SYSTEM,
        metadata=TemplateMetadata(
            version="1.0",
            author="msc-sql",
            tags=["table_linking"],
        ),
    )

    direct_generation_prompt: PromptTemplate = PromptTemplate(
        template=f"""{_gen_prefix}

**Yêu cầu**: Hãy suy nghĩ từng bước và giải quyết câu hỏi bằng cách đưa ra câu lệnh SQL chính xác để giải quyết câu hỏi. Bạn có khả năng chọn lọc và cung cấp thông tin **dễ hiểu**, **có ngữ nghĩa** khi trả lời câu hỏi, ngay cả khi phải tham chiếu qua nhiều bảng. Kết quả sau khi truy vấn phải dễ hiểu, hữu ích khiến người dùng cuối thực sự muốn thấy và có thể hiểu được.

---

**Lưu ý**:
1. Chỉ sử dụng các bảng được cung cấp để giải quyết nhiệm vụ. Không tự ý tạo ra tên bảng hoặc tên cột.
2. Sử dụng "bằng chứng" và các bản ghi mẫu cùng mô tả cột được cung cấp để lập luận.
3. Đừng quên các từ khóa như DISTINCT, WHERE, GROUP BY, ORDER BY, LIMIT,... nếu cần thiết.
1. Chỉ chọn những cột mang ý nghĩa diễn giải, thân thiện với người dùng (ví dụ: fullname, name, title, description...). Tránh chọn các ID nếu không thực sự cần thiết.
    - Luôn chọn `full_name` thay vì `id`, `name` thay vì `code` (nếu schema cho phép).
    - Nếu một bảng chính trong truy vấn (ví dụ: `product_variants`) không có trường tên/mô tả trực tiếp, nhưng có liên kết (qua khóa ngoại) đến một bảng khác chứa thông tin tên/mô tả liên quan (ví dụ: `products.product_name`), **hãy thực hiện `JOIN` để lấy và hiển thị trường tên/mô tả đó.** Ví dụ: hiển thị `products.name` cho một `product_variant_id` thay vì chỉ hiển thị `product_variants.product_id`.
1. Bao gồm cả ID nếu hữu ích hoặc cần thiết:
    - Nếu người dùng yêu cầu ID một cách rõ ràng trong câu hỏi.
    - Nếu ID là cách duy nhất để xác định một mục một cách duy nhất (ví dụ: khi tên/mô tả có thể trùng lặp).
    - Thường thì việc hiển thị cả ID và tên/mô tả (ví dụ: `SELECT user_id, user_fullname FROM users`) sẽ hữu ích hơn là chỉ hiển thị tên, đặc biệt nếu ID có thể được sử dụng cho các thao tác hoặc tra cứu tiếp theo. Hãy cân nhắc điều này.

2. Tự động mở rộng thông tin khi cần:
   - Ví dụ: Khi câu hỏi hỏi về "đơn hàng", không chỉ trả về `order.id` mà nên bao gồm cả `customer.full_name`, `product.name`, `order.total_amount`.
2. Nếu bảng chính không có trường diễn giải, hãy JOIN sang bảng liên quan để lấy trường mô tả (ví dụ: thay vì product_variant.product_id → JOIN sang product để lấy product.name).
Không suy đoán ngoài dữ liệu và schema đã cung cấp.

---

**Đầu vào**:
- Câu hỏi SQL: {{question}}
- Cấu trúc cơ sở dữ liệu: {{schema}}
- Bằng chứng: {{evidence}}
- Nhắc lại câu hỏi SQL: {{question}}
        """,
    )
    query_fixing_prompt: PromptTemplate = PromptTemplate(
        template="""
**Câu hỏi của người dùng**: {question}

**Câu truy vấn SQL**: 
```sql
{query}
```

**KIỂM TRA KỸ LƯỠNG câu truy vấn {dialect} ở trên để tìm các lỗi phổ biến, bao gồm:**
- Sử dụng NOT IN với các giá trị NULL
- Sử dụng UNION khi nên dùng UNION ALL
- Sử dụng BETWEEN cho các khoảng không bao gồm biên
- Không khớp kiểu dữ liệu trong các điều kiện
- Đặt tên định danh trong dấu ngoặc kép đúng cách
- Sử dụng đúng số lượng tham số cho các hàm
- Ép kiểu sang đúng kiểu dữ liệu
- Sử dụng đúng cột cho các phép nối

Nếu có bất kỳ lỗi nào trong số các lỗi trên, trả về `false`. Nếu không có lỗi nào, chỉ cần trả về `true`.
        """,
    )
    response_enhancement_prompt: PromptTemplate = PromptTemplate(
        template="""
Bạn nhận được **KẾT QUẢ** câu truy vấn SQL và **CÂU HỎI** của người dùng. Hãy cải thiện kết quả sau khi truy vấn SQL cho phù hợp với câu hỏi của người dùng.

**Câu hỏi của người dùng**: {question}

**Kết quả truy vấn SQL**: {result}
        
        """,
    )
    user_prompt: PromptTemplate = PromptTemplate(
        template="{question}",
        role=Role.USER,
    )

    assistant_prompt: PromptTemplate = PromptTemplate(
        template="{sql_query}",
        role=Role.ASSISTANT,
    )

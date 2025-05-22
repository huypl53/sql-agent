from sql_qa.prompt.template import PromptTemplate, Role, TemplateMetadata
from sql_qa.config import get_app_config

app_config = get_app_config()


class PromptConstant:
    _gen_prefix = """
    **CHÚ Ý**: 
    - Phải tuân thủ đúng cú pháp của câu lệnh SQL và các quy tắc của {dialect}.
    - Câu truy vấn SQL phải chứa thông tin có ý nghĩa và dễ hiểu cho người dùng.
    
    """.format(
        dialect=app_config.database.dialect.upper()
    )
    _gen_suffix = """
    **Đầu vào**:
    - Câu hỏi SQL: {question}
    - Cấu trúc cơ sở dữ liệu: {schema}
    - Bằng chứng: {evidence}
    - Nhắc lại câu hỏi SQL: {question}

    --- 
    
    **Đầu ra**:
    - Câu lệnh SQL: 
    - Giải thích: 
    """
    system: PromptTemplate = PromptTemplate(
        template="""
Là một quản trị viên cơ sở dữ liệu chuyên nghiệp và giàu kinh nghiệm, nhiệm vụ của bạn là phân tích câu hỏi của người dùng và lược đồ cơ sở dữ liệu {dialect} để cung cấp thông tin liên quan. Bạn được cung cấp `Câu hỏi` của người dùng và `Lược đồ DB` chứa cấu trúc cơ sở dữ liệu.
        """,
        role=Role.SYSTEM,
        metadata=TemplateMetadata(
            version="1.0",
            author="msc-sql",
            tags=["system"],
        ),
    )
    table_linking: PromptTemplate = PromptTemplate(
        template="""
Hãy suy nghĩ từng bước. Xác định và liệt kê tất cả các tên bảng liên quan từ lược đồ DB dựa trên câu hỏi của người dùng và lược đồ cơ sở dữ liệu được cung cấp. Hãy đảm bảo bạn bao gồm tất cả các bảng liên quan.

**Câu hỏi SQL**: {question}

**Lược đồ DB**: {schema}

**Kết quả**:
- Trả về danh sách tên các bảng liên quan được phân cách bằng dấu phẩy theo định dạng: "bảng1, bảng2, bảng3"
        """,
        role=Role.ASSISTANT,
        metadata=TemplateMetadata(
            version="1.0",
            author="msc-sql",
            tags=["table_linking"],
        ),
    )

    direct_generation: PromptTemplate = PromptTemplate(
        template=f"""
{_gen_prefix}

**Yêu cầu**: Hãy suy nghĩ từng bước và giải quyết câu hỏi bằng cách đưa ra câu lệnh SQL chính xác để giải quyết câu hỏi. Bạn có khả năng chọn lọc và cung cấp thông tin **dễ hiểu**, **có ngữ nghĩa** khi trả lời câu hỏi, ngay cả khi phải tham chiếu qua nhiều bảng. Kết quả sau khi truy vấn phải dễ hiểu, hữu ích khiến người dùng cuối thực sự muốn thấy và có thể hiểu được.

---

**Lưu ý**:
1. Chỉ sử dụng các bảng được cung cấp để giải quyết nhiệm vụ. Không tự ý tạo ra tên bảng hoặc tên cột.
2. Sử dụng "bằng chứng" và các bản ghi mẫu cùng mô tả cột được cung cấp để lập luận.
3. Đừng quên các từ khóa như DISTINCT, WHERE, GROUP BY, ORDER BY, LIMIT,... nếu cần thiết.
4. Chỉ chọn những cột mang ý nghĩa diễn giải, thân thiện với người dùng (ví dụ: fullname, name, title, description...). Tránh chọn các ID nếu không thực sự cần thiết.
    - Luôn chọn `full_name` thay vì `id`, `name` thay vì `code` (nếu schema cho phép).
    - Nếu một bảng chính trong truy vấn (ví dụ: `product_variants`) không có trường tên/mô tả trực tiếp, nhưng có liên kết (qua khóa ngoại) đến một bảng khác chứa thông tin tên/mô tả liên quan (ví dụ: `products.product_name`), **hãy thực hiện `JOIN` để lấy và hiển thị trường tên/mô tả đó.** Ví dụ: hiển thị `products.name` cho một `product_variant_id` thay vì chỉ hiển thị `product_variants.product_id`.
5. Bao gồm cả ID nếu hữu ích hoặc cần thiết:
    - Nếu người dùng yêu cầu ID một cách rõ ràng trong câu hỏi.
    - Nếu ID là cách duy nhất để xác định một mục một cách duy nhất (ví dụ: khi tên/mô tả có thể trùng lặp).
    - Thường thì việc hiển thị cả ID và tên/mô tả (ví dụ: `SELECT user_id, user_fullname FROM users`) sẽ hữu ích hơn là chỉ hiển thị tên, đặc biệt nếu ID có thể được sử dụng cho các thao tác hoặc tra cứu tiếp theo. Hãy cân nhắc điều này.

6. Tự động mở rộng thông tin khi cần:
    - Ví dụ: Khi câu hỏi hỏi về "đơn hàng", không chỉ trả về `order.id` mà nên bao gồm cả `customer.full_name`, `product.name`, `order.total_amount`.
7. Nếu bảng chính không có trường diễn giải, hãy JOIN sang bảng liên quan để lấy trường mô tả (ví dụ: thay vì product_variant.product_id → JOIN sang product để lấy product.name).

Không suy đoán ngoài dữ liệu và schema đã cung cấp.

---

{_gen_suffix}
        """,
    )
    cot_generation: PromptTemplate = PromptTemplate(
        template=f"""
{_gen_prefix}

**Yêu cầu**: Hãy suy nghĩ từng bước và giải quyết câu hỏi bằng cách đưa ra câu lệnh SQL chính xác để giải quyết câu hỏi. Bạn có khả năng chọn lọc và cung cấp thông tin **dễ hiểu**, **có ngữ nghĩa** khi trả lời câu hỏi, ngay cả khi phải tham chiếu qua nhiều bảng. Kết quả sau khi truy vấn phải dễ hiểu, hữu ích khiến người dùng cuối thực sự muốn thấy và có thể hiểu được.

**Mô tả nhiệm vụ**:
Bạn là chuyên gia SQL có nhiệm vụ tạo câu truy vấn SQL dựa trên câu hỏi của người dùng.

**Quy trình**: 
**Bước 1: Phân tích Câu hỏi SQL**
- Đọc kỹ câu hỏi: "{{question}}"
- Xác định mục tiêu chính của câu hỏi: Người dùng muốn biết thông tin gì? Có cần thống kê, lọc, sắp xếp không?
- Gạch chân các thực thể (ví dụ: người dùng, sản phẩm, đơn hàng) và các điều kiện/tiêu chí (ví dụ: ngày, số lượng, trạng thái).

**Bước 2: Xác định Bảng và Liên kết (JOIN) cần thiết**
- Dựa vào Bước 1 và `Cấu trúc cơ sở dữ liệu: {{schema}}`, hãy liệt kê các bảng có khả năng chứa thông tin liên quan.
- Kiểm tra `Bằng chứng: {{evidence}}` để hiểu rõ hơn về mối quan hệ giữa các bảng và ý nghĩa của các cột.
- Nếu cần thông tin từ nhiều bảng, hãy xác định các mối quan hệ (ví dụ: khóa chính/khóa ngoại) và quyết định loại JOIN (INNER JOIN, LEFT JOIN, v.v.) phù hợp. Mục tiêu là thu thập tất cả dữ liệu cần thiết để trả lời câu hỏi.

**Bước 3: Xác định Điều kiện Lọc (WHERE Clause)**
- Dựa vào các tiêu chí đã xác định ở Bước 1, hãy xây dựng các điều kiện `WHERE` để thu hẹp kết quả.
- Kiểm tra các kiểu dữ liệu và toán tử phù hợp (ví dụ: `>`, `<`, `=`, `LIKE`, `IN`).

**Bước 4: Xác định Nhóm và Tổng hợp (GROUP BY & Aggregate Functions)**
- Nếu câu hỏi yêu cầu tính tổng, trung bình, đếm, hoặc các phép toán thống kê khác, hãy xác định các hàm tổng hợp (COUNT, SUM, AVG, MAX, MIN).
- Xác định các cột mà kết quả cần được nhóm theo (GROUP BY).

**Bước 5: Xác định Sắp xếp và Giới hạn (ORDER BY & LIMIT)**
- Nếu câu hỏi yêu cầu sắp xếp kết quả (ví dụ: theo ngày, theo giá trị cao nhất/thấp nhất), hãy xác định cột và thứ tự sắp xếp (`ASC` hoặc `DESC`).
- Nếu câu hỏi yêu cầu chỉ lấy một số lượng kết quả nhất định (ví dụ: top 5, 3 sản phẩm gần đây nhất), hãy xác định `LIMIT`.

**Bước 6: Chọn Cột Hiển thị trong SELECT (User-Friendly Output Strategy)**
- Đây là bước **quan trọng nhất** để đảm bảo kết quả dễ hiểu cho người dùng.
- **Mục tiêu:** Chọn các cột `SELECT` sẽ mang lại thông tin trực quan, dễ đọc và có ý nghĩa cho người dùng cuối.
- **Ưu tiên cao nhất:** Luôn ưu tiên các cột có tính mô tả rõ ràng như `name`, `title`, `description`, `fullname`, `email`, `product_name`, `category_name`, `order_date`, `status`, `address`, `phone_number`.
- **Tránh dùng ID trực tiếp:** Tránh chọn trực tiếp các cột ID (`id`, `user_id`, `product_id`, `order_id`) làm kết quả hiển thị, trừ khi:
    - Câu hỏi *chỉ định rõ ràng* cần trả về ID (ví dụ: "Liệt kê ID của tất cả người dùng").
    - Hoặc không có bất kỳ cột mô tả nào khác phù hợp để thay thế.
- **Tham chiếu chéo cho thông tin diễn giải:**
    - Nếu một bảng (ví dụ: `product_variant`) chỉ chứa `product_id` nhưng không có tên riêng, hãy **bắt buộc** thực hiện JOIN với bảng `product` để lấy `product.name` hoặc `product.title` để diễn giải rõ ràng biến thể đó là của sản phẩm nào.
    - Áp dụng nguyên tắc tương tự cho các bảng khác (ví dụ: `order_item` cần `product.name`, `user_address` cần `user.fullname`).
- **Sử dụng AS (Alias):** Nếu tên cột dài hoặc không rõ ràng, hãy sử dụng `AS` để đặt biệt danh (alias) dễ đọc hơn cho các cột trong kết quả trả về.

**Bước 7: Tổng hợp Câu lệnh SQL và Kiểm tra Lại**
- Kết hợp tất cả các thành phần đã xác định ở các bước trên thành một câu lệnh SQL hoàn chỉnh.
- Đọc lại câu lệnh SQL và đối chiếu với:
    - Mục tiêu ban đầu của câu hỏi.
    - Tất cả các "Nguyên tắc Quan trọng" và "Quá trình suy nghĩ từng bước", đặc biệt là về việc lựa chọn cột hiển thị.
    - Cấu trúc cơ sở dữ liệu và bằng chứng.
- Đảm bảo rằng câu lệnh không chỉ đúng về mặt cú pháp mà còn tối ưu về mặt hiệu suất và cung cấp thông tin *giá trị nhất* cho người dùng.

**Định dạng đầu ra**:  Trình bày câu truy vấn đã sửa của bạn dưới dạng một dòng mã SQL duy nhất, sau phần Kết quả cuối cùng. Đảm bảo không có ngắt dòng trong câu truy vấn.  

Dưới đây là một số ví dụ: {{examples}} 

---

{_gen_suffix}
        """,
    )

    dat_cot_genration = PromptTemplate(
        template=f"""
{_gen_prefix}
Bạn là một chuyên gia chuyển đổi câu hỏi tự nhiên thành câu lệnh SQL. Mục tiêu của bạn là tạo ra câu lệnh SQL chính xác, tối ưu, và đặc biệt là *cung cấp kết quả dễ hiểu, có ý nghĩa cho người dùng cuối*.

**Những Nguyên tắc Quan trọng Chung:**
1.  Chỉ sử dụng các bảng cần thiết để giải quyết nhiệm vụ.
2.  Sử dụng "Cấu trúc cơ sở dữ liệu" và "Bằng chứng" để lập luận và xác định các mối quan hệ.
3.  Đảm bảo sử dụng các từ khóa SQL (DISTINCT, WHERE, GROUP BY, ORDER BY, LIMIT, JOIN, Subqueries/CTEs) khi cần.
4.  **Ưu tiên Hiển thị Thông tin Dễ Đọc và Ý Nghĩa (User-Friendly Output):**
    *   Khi chọn các cột để hiển thị trong câu lệnh `SELECT` cuối cùng (kết quả trả về cho người dùng), *luôn ưu tiên* các cột mang ý nghĩa, dễ đọc và cung cấp thông tin trực quan (ví dụ: `name`, `title`, `description`, `fullname`, `email`, `product_name`, `category_name`, `order_date`, `status`, `address`, `phone_number`).
    *   Nếu một bảng không có cột mô tả trực tiếp nhưng có thể tham chiếu đến một bảng khác để lấy thông tin mô tả liên quan (ví dụ: bảng `product_variant` chỉ có `product_id`, cần `product.name` để giải thích biến thể là của sản phẩm nào), hãy thực hiện các thao tác JOIN cần thiết và chọn cột mô tả từ bảng liên quan.
    *   Chỉ trả về các cột ID nếu câu hỏi SQL yêu cầu *cụ thể* ID, hoặc nếu không có bất kỳ cột mô tả nào khác phù hợp.
    *   Sử dụng `AS` (Alias) để đặt tên cột thân thiện hơn nếu tên gốc khó hiểu.
---
**Cấu trúc cơ sở dữ liệu:** {{schema}}
**Bằng chứng (Các bản ghi mẫu và mô tả cột):** {{evidence}}
**Câu hỏi SQL:** {{question}}
**Gợi ý (nếu có):** {{hint}}

---

**Quá trình suy nghĩ theo chiến lược "Chia để Trị" (Chain-of-Thought):**
**1. Chia để Trị (Divide and Conquer):**
*   **1.1. Câu hỏi Chính:** {{question}}
    *   **Phân tích Mục tiêu & Chiến lược Output ban đầu:**
        *   Xác định rõ ràng mục tiêu chính của câu hỏi: Người dùng muốn biết thông tin gì?
        *   Xác định các thực thể chính liên quan và các điều kiện tổng thể.
        *   Dựa trên "Nguyên tắc Quan trọng Chung số 4", phác thảo các cột `SELECT` dự kiến sẽ mang lại thông tin hữu ích và dễ đọc cho người dùng cuối.
    *   **Pseudo SQL (Khởi tạo):**
        ```
        SELECT [các cột thân thiện người dùng]
        FROM [bảng chính]
        WHERE [điều kiện tổng thể]
        ```
*   **1.2. Phân tích Câu hỏi Phụ (Sub-questions):**
    *   Chia câu hỏi chính thành các câu hỏi nhỏ hơn, độc lập có thể giải quyết được.
    *   Đối với mỗi câu hỏi phụ, hãy làm rõ:
        *   **Câu hỏi Phụ X:** [Tóm tắt câu hỏi phụ]
        *   **Phân tích & Lập luận:**
            *   Làm thế nào để giải quyết câu hỏi phụ này?
            *   Các bảng cần thiết và mối quan hệ JOIN.
            *   Các điều kiện lọc (WHERE), nhóm (GROUP BY), sắp xếp (ORDER BY), giới hạn (LIMIT) áp dụng cho câu hỏi phụ này.
            *   Lưu ý: Các cột được chọn trong câu hỏi phụ có thể là ID hoặc các cột cần thiết cho việc lọc/JOIN tiếp theo, không nhất thiết phải là các cột hiển thị thân thiện người dùng ở bước này.
        *   **Pseudo SQL:**
            ```
            [Pseudo SQL cho câu hỏi phụ X]
            ```
    *   ...(Lặp lại cho các câu hỏi phụ khác nếu cần, ví dụ: 1.3, 1.4)
**2. Tổng hợp SQL từ các Bước Phụ (Assembling SQL):**
*   Từ các Pseudo SQL đã phác thảo, chuyển đổi chúng thành các câu lệnh SQL cụ thể, bắt đầu từ câu hỏi phụ sâu nhất (hoặc đơn giản nhất) và xây dựng lên.
*   **2.1. SQL Câu hỏi Phụ X ([Mô tả]):**
    *   **SQL:**
        ```sql
        [SQL cụ thể cho câu hỏi phụ X]
        ```
*   **2.2. SQL Câu hỏi Phụ Y ([Mô tả]):**
    *   **SQL:**
        ```sql
        [SQL cụ thể cho câu hỏi phụ Y, có thể sử dụng kết quả từ X nếu cần]
        ```
*   **2.3. SQL Câu hỏi Chính ([Mô tả]):**
    *   **SQL:**
        ```sql
        [SQL cụ thể cho câu hỏi chính, tích hợp kết quả từ các câu hỏi phụ]
        ```
**3. Đơn giản hóa và Tối ưu hóa (Simplification and Optimization):**
*   Phân tích câu lệnh SQL tổng hợp từ Bước 2.
*   Tìm cách tối ưu hóa hiệu suất và độ rõ ràng:
    *   Kết hợp các truy vấn lồng nhau (subqueries) thành một truy vấn duy nhất bằng cách sử dụng JOIN hoặc CTEs (Common Table Expressions) nếu phù hợp.
    *   Đảm bảo rằng các chỉ mục (index) tiềm năng có thể được sử dụng hiệu quả.
    *   Kiểm tra lại toàn bộ câu lệnh theo các "Nguyên tắc Quan trọng Chung" và đặc biệt là "Ưu tiên Hiển thị Thông tin Dễ Đọc và Ý Nghĩa". Đảm bảo các cột `SELECT` cuối cùng đã được tối ưu cho người dùng.

---
{_gen_suffix}
""",
    )

    qp_generation: PromptTemplate = PromptTemplate(
        template=f"""
{_gen_prefix}
Bạn là một chuyên gia chuyển đổi câu hỏi tự nhiên thành câu lệnh SQL. Nhiệm vụ của bạn là tạo ra một câu lệnh SQL chính xác, hiệu quả và *quan trọng nhất là cung cấp kết quả dễ đọc, có ý nghĩa cho người dùng cuối*.

**Những Nguyên tắc Quan trọng Chung:**
1.  Chỉ sử dụng các bảng cần thiết để giải quyết nhiệm vụ.
2.  Sử dụng "Cấu trúc cơ sở dữ liệu" và "Bằng chứng" để lập luận, xác định các mối quan hệ và ý nghĩa dữ liệu.
3.  Đảm bảo sử dụng các từ khóa SQL (DISTINCT, WHERE, GROUP BY, ORDER BY, LIMIT, JOIN, Subqueries/CTEs) khi cần thiết.
4.  **Ưu tiên Hiển thị Thông tin Dễ Đọc và Ý Nghĩa (User-Friendly Output):**
    *   Khi chọn các cột để hiển thị trong câu lệnh `SELECT` cuối cùng, *luôn ưu tiên* các cột mang ý nghĩa, dễ đọc và cung cấp thông tin trực quan (ví dụ: `name`, `title`, `description`, `fullname`, `email`, `product_name`, `category_name`, `order_date`, `status`, `address`, `phone_number`).
    *   Nếu một bảng không có cột mô tả trực tiếp nhưng có thể tham chiếu đến một bảng khác để lấy thông tin mô tả liên quan (ví dụ: `product_variant` cần `product.name`), hãy thực hiện các thao tác JOIN cần thiết và chọn cột mô tả từ bảng liên quan.
    *   Chỉ trả về các cột ID nếu câu hỏi SQL yêu cầu *cụ thể* ID, hoặc nếu không có bất kỳ cột mô tả nào khác phù hợp.
    *   Sử dụng `AS` (Alias) để đặt tên cột thân thiện hơn nếu tên gốc khó hiểu (ví dụ: `client.A11 AS average_salary_branch`).

---

**Cấu trúc cơ sở dữ liệu:** {{schema}}
**Bằng chứng (Các bản ghi mẫu và mô tả cột):** {{evidence}}

**Câu hỏi SQL:** {{question}}
**Gợi ý (nếu có):** {{hint}}

---

**Quá trình suy nghĩ theo Kế hoạch Truy vấn (Query Plan - Chain-of-Thought):**

**1. Phân tích Yêu cầu và Xác định Mục tiêu:**
*   Đọc kỹ câu hỏi: "{{question}}"
*   Xác định mục tiêu chính của câu hỏi: Người dùng muốn biết thông tin gì?
*   Xác định các thực thể chính và điều kiện liên quan.
*   **Xác định Output Mong muốn (theo Nguyên tắc 4):** Những loại thông tin (tên, mô tả, số lượng, v.v.) nào cần được hiển thị cho người dùng cuối và chúng sẽ đến từ những bảng nào?

**2. Xây dựng Kế hoạch Truy vấn (Query Plan):**
*   Hãy tưởng tượng bạn là một công cụ tối ưu hóa truy vấn của cơ sở dữ liệu. Hãy phác thảo các bước mà hệ thống sẽ thực hiện để xử lý câu hỏi này, từ việc truy cập dữ liệu thô đến việc tạo ra kết quả cuối cùng.

*   **2.1. Giai đoạn Chuẩn bị & Khởi tạo:**
    *   Xác định các bảng dữ liệu gốc cần được truy cập ngay từ đầu.
    *   Mô tả cách "mở" các bảng này và "khởi tạo" các biến hoặc vùng nhớ tạm thời .
    *   Xác định các giá trị cố định (literal values) cần tìm kiếm .

*   **2.2. Giai đoạn Lọc và Kết nối Dữ liệu (JOIN & WHERE Logic):**
    *   Mô tả luồng dữ liệu khi nó được lọc ban đầu.
    *   Giải thích các điều kiện `WHERE` sẽ được áp dụng cho từng bảng.
    *   Chi tiết cách các bảng sẽ được `JOIN` với nhau, và lý do cho mỗi `JOIN`.
    *   Mô tả thứ tự các phép lọc và kết nối.
    *   Trong bước này, các cột được chọn có thể là ID hoặc các cột cần thiết cho việc lọc/JOIN tiếp theo, không nhất thiết là các cột hiển thị cuối cùng.

*   **2.3. Giai đoạn Xử lý Dữ liệu (Nhóm, Tổng hợp, Sắp xếp, Giới hạn):**
    *   Nếu câu hỏi yêu cầu thống kê (ví dụ: đếm, tổng, trung bình), mô tả cách các phép toán tổng hợp (`COUNT`, `SUM`, `AVG`, `MAX`, `MIN`) sẽ được áp dụng.
    *   Xác định các cột dùng để nhóm (`GROUP BY`).
    *   Giải thích cách dữ liệu sẽ được sắp xếp (`ORDER BY`) và giới hạn (`LIMIT`) nếu có yêu cầu.

*   **2.4. Giai đoạn Lựa chọn Cột Cuối cùng và Định dạng (Final SELECT & Presentation):**
    *   **Đây là bước quyết định để áp dụng Nguyên tắc 4.** Dựa trên tất cả dữ liệu đã được xử lý và lọc ở các bước trước, hãy xác định *chính xác* các cột sẽ được đưa vào mệnh đề `SELECT` cuối cùng.
    *   Lập luận về việc chọn các cột dễ đọc, có ý nghĩa (`name`, `fullname`, v.v.) thay vì ID.
    *   Nếu cần JOIN để lấy thông tin mô tả (ví dụ: từ `product_variant` lấy `product.name`), hãy đảm bảo bước này đã được mô tả ở 2.2 và kết quả `name` được chọn ở đây.
    *   Đề xuất sử dụng `AS` để đặt biệt danh thân thiện cho các cột nếu cần.

*   **2.5. Giai đoạn Kết thúc & Trả Về Kết quả:**
    *   Mô tả cách kết quả cuối cùng được trả về.

**3. Tổng hợp Câu lệnh SQL:**
*   Kết hợp tất cả các bước trong Query Plan thành một câu lệnh SQL hoàn chỉnh, tối ưu.
*   Đảm bảo câu lệnh tuân thủ tất cả các "Nguyên tắc Quan trọng Chung", đặc biệt là về việc lựa chọn cột hiển thị và các Alias (AS) đã đề xuất.
*   Kiểm tra lại tính đúng đắn và hiệu quả.

---
{_gen_suffix}
""",
    )

    query_fixing: PromptTemplate = PromptTemplate(
        template=f"""
{_gen_prefix}

**Mô tả nhiệm vụ**: 
Bạn là một chuyên gia cơ sở dữ liệu SQL được giao nhiệm vụ sửa một câu truy vấn SQL. Một lần thử chạy truy vấn trước đó không cho kết quả chính xác, có thể do lỗi khi thực thi hoặc vì kết quả trả về trống hoặc không như mong đợi. Nhiệm vụ của bạn là phân tích lỗi dựa trên lược đồ cơ sở dữ liệu được cung cấp và chi tiết của lần thực thi thất bại, sau đó cung cấp phiên bản đã sửa của câu truy vấn SQL.  

**Lưu ý**:
1. Chỉ sử dụng các bảng được cung cấp để giải quyết nhiệm vụ. Không tự ý tạo ra tên bảng hoặc tên cột.
2. Sử dụng "bằng chứng" và các bản ghi mẫu cùng mô tả cột được cung cấp để lập luận.
3. Đừng quên các từ khóa như DISTINCT, WHERE, GROUP BY, ORDER BY, LIMIT,... nếu cần thiết.

**Quy trình**: 
1. Xem xét lược đồ cơ sở dữ liệu: 
- Kiểm tra các câu lệnh tạo bảng để hiểu cấu trúc cơ sở dữ liệu. 
2. Phân tích yêu cầu truy vấn: 
- Câu hỏi gốc: Xem xét thông tin mà truy vấn cần truy xuất. 
- Gợi ý: Sử dụng các gợi ý được cung cấp để hiểu các mối quan hệ và điều kiện liên quan đến truy vấn. 
- Câu truy vấn SQL đã thực thi: Xem xét câu truy vấn SQL đã được thực thi trước đó và dẫn đến lỗi hoặc kết quả không chính xác. 
- Kết quả thực thi: Phân tích kết quả của câu truy vấn đã thực thi để xác định lý do tại sao nó thất bại (ví dụ: lỗi cú pháp, tham chiếu cột không chính xác, lỗi logic). 
3. Sửa câu truy vấn: 
- Sửa đổi câu truy vấn SQL để giải quyết các vấn đề đã xác định, đảm bảo nó truy xuất dữ liệu được yêu cầu một cách chính xác theo lược đồ cơ sở dữ liệu và yêu cầu truy vấn.  

**Định dạng đầu ra**:  Trình bày câu truy vấn đã sửa của bạn dưới dạng một dòng mã SQL duy nhất, sau phần Kết quả cuối cùng. Đảm bảo không có ngắt dòng trong câu truy vấn.  

======= Nhiệm vụ của bạn ======= 
************************** 
Các câu lệnh tạo bảng 
{{schema}} 
************************** 
Câu hỏi gốc là: 
- Câu hỏi: {{question}} 
- Bằng chứng: {{evidence}} 
- Câu truy vấn SQL đã thực thi là: {{query}} 
- Kết quả thực thi: {{result}} 
************************** 
Dựa trên câu hỏi, lược đồ bảng và câu truy vấn trước đó, phân tích kết quả và cố gắng sửa câu truy vấn.       

        """,
        role=Role.SYSTEM,
        metadata=TemplateMetadata(
            version="1.0",
            author="msc-sql",
            tags=["query_fixing"],
        ),
    )
    query_validation: PromptTemplate = PromptTemplate(
        template=f"""
{_gen_prefix}
**Mô tả nhiệm vụ**:
Bạn là chuyên gia SQL có nhiệm vụ kiểm tra tính hợp lệ của câu truy vấn SQL.

**Câu hỏi của người dùng**: {{question}}

**Câu truy vấn SQL**: 
```sql
{{query}}
```

**KIỂM TRA KỸ LƯỠNG câu truy vấn {{dialect}} ở trên để tìm các lỗi phổ biến, bao gồm**:
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
    response_enhancement: PromptTemplate = PromptTemplate(
        template="""
Bạn nhận được **KẾT QUẢ GỐC** sau khi đã được truy vấn từ cơ sở dữ liệu, **CÂU HỎI** của người dùng và câu lệnh SQL đã được sử dụng. Hãy cải thiện **KẾT QUẢ GỐC** để tạo thành câu trả lời tự nhiên, dễ hiểu, phù hợp với **CÂU HỎI** của người dùng.

**Câu hỏi của người dùng**: {question}

**Câu lệnh SQL đã sử dụng**: {sql_query}

**Kết quả truy vấn SQL**: {result}

**Kết quả cải thiện**:
        """,
    )

    merger: PromptTemplate = PromptTemplate(
        template=f"""
{_gen_prefix}

**Mô tả nhiệm vụ**:
Bạn là một chuyên gia SQL có nhiệm vụ tổng hợp các câu lệnh truy vấn SQL candidate thành một câu lệnh SQL cuối cùng. Dựa trên câu hỏi của người dùng, lược đồ cơ sở dữ liệu, và các câu lệnh SQL candidate được cung cấp, hãy phân tích và chọn ra câu lệnh SQL tốt nhất hoặc kết hợp các phần tốt nhất từ các candidate để tạo ra câu lệnh SQL cuối cùng.

**Quy trình**:
1. **Phân tích câu hỏi**: Đọc kỹ câu hỏi của người dùng để hiểu rõ yêu cầu.
2. **Xem xét lược đồ cơ sở dữ liệu**: Kiểm tra cấu trúc cơ sở dữ liệu để đảm bảo câu lệnh SQL cuối cùng phù hợp với lược đồ.
3. **Đánh giá các câu lệnh SQL candidate**:
   - Kiểm tra tính chính xác của cú pháp.
   - Đánh giá hiệu suất và tối ưu hóa.
   - Xem xét khả năng cung cấp thông tin dễ hiểu và có ý nghĩa cho người dùng.
4. **Tổng hợp câu lệnh SQL cuối cùng**:
   - Chọn câu lệnh SQL tốt nhất từ các candidate.
   - Hoặc kết hợp các phần tốt nhất từ các candidate để tạo ra câu lệnh SQL cuối cùng.
5. **Kiểm tra lại**: Đảm bảo câu lệnh SQL cuối cùng đáp ứng đúng yêu cầu của câu hỏi và tuân thủ các nguyên tắc SQL.

**Định dạng đầu ra**: Trình bày câu lệnh SQL cuối cùng dưới dạng một dòng mã SQL duy nhất, sau phần Kết quả cuối cùng. Đảm bảo không có ngắt dòng trong câu lệnh.

**Các câu lệnh SQL candidate**:
{{candidates}}

**Kết quả cuối cùng**:
        """,
    )
    user: PromptTemplate = PromptTemplate(
        template="{question}",
        role=Role.USER,
    )

    assistant: PromptTemplate = PromptTemplate(
        template="{sql_query}",
        role=Role.ASSISTANT,
    )

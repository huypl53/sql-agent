from typing import TypedDict, Any
from enum import Enum

class EColumn(Enum):
    role = 'role'
    question = 'question'
    gt_sql = 'gt_sql'
    gt_execution = 'gt_execution'
    gt_schema = 'gt_schema'
    
    gen_sql = 'gen_sql'
    gen_execution = 'gen_execution'
    gen_response = 'gen_response'
    gen_sql_error = 'gen_sql_error'
    gen_schema = 'gen_schema'
    
    em = 'em'
    ex = 'ex'
    
    llm_judge_em = 'llm_judge_em'
    llm_judge_ex = 'llm_judge_ex'


class LogRowEntry(TypedDict):
    created_date:Any
    user_question:Any
    linking_structured_result:Any
    filtered_schema_tables:Any
    direct_generation_prompt:Any
    generation_response:Any
    query_validation_prompt:Any
    query_validation_response:Any
    final_sql:Any
    cot_generation_prompt:Any
    dac_cot_genration_prompt:Any
    query_plan_generation_prompt:Any
    merger_prompt:Any
    merger_response:Any
    merger_result:Any
    sql_result:Any
    response_enhancement_prompt:Any
    response_enhancement_response:Any
    response_enhancement_result:Any
    query_fixing_prompt:Any
    query_fixing_response: Any      

class LlmRowEntry(TypedDict):
    question: Any
    ground_truth_sql: Any
    level: Any
    ground_truth_result: Any
    error: Any
    generated_sql_query: Any
    generated_query_result: Any
    generated_sql_error: Any
    generated_raw_result: Any
    llm_exact_match: Any
    llm_execution_match: Any

    candidate_generations: Any
    candidate_em: Any
    candidate_ex: Any
    candidate_least_correct: Any
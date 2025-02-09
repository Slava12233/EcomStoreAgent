from utils.logger import debug_logger, error_logger
from langchain.callbacks.base import BaseCallbackHandler
from typing import Any, Dict, List, Union

class CustomCallbackHandler(BaseCallbackHandler):
    """מחלקה מותאמת לטיפול בקולבקים של LangChain"""
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """מתעד תחילת קריאה ל-LLM"""
        debug_logger.debug("-" * 50)
        debug_logger.debug("Starting LLM call")
        for i, prompt in enumerate(prompts, 1):
            debug_logger.debug(f"Prompt {i}:\n{prompt}")
    
    def on_llm_end(self, response: Any, **kwargs) -> None:
        """מתעד סיום קריאה ל-LLM"""
        debug_logger.debug(f"LLM Response:\n{response}")
        debug_logger.debug("-" * 50)
    
    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """מתעד שגיאות בקריאה ל-LLM"""
        error_logger.error(f"LLM error: {str(error)}", exc_info=True)
        debug_logger.debug("-" * 50)

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """מתעד תחילת שרשרת עיבוד"""
        debug_logger.debug(f"Starting chain: {serialized.get('name', 'unnamed')}")
        debug_logger.debug(f"Chain inputs: {inputs}")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """מתעד סיום שרשרת עיבוד"""
        debug_logger.debug(f"Chain outputs: {outputs}")

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """מתעד תחילת שימוש בכלי"""
        debug_logger.debug(f"Starting tool: {serialized.get('name', 'unnamed')}")
        debug_logger.debug(f"Tool input: {input_str}")

    def on_tool_end(self, output: str, **kwargs) -> None:
        """מתעד סיום שימוש בכלי"""
        debug_logger.debug(f"Tool output: {output}")

    def on_text(self, text: str, **kwargs) -> None:
        """מתעד טקסט שנוצר במהלך העיבוד"""
        debug_logger.debug(f"Generated text: {text}")

async def process_message(message: str) -> str:
    """עיבוד הודעת משתמש באמצעות LLM"""
    try:
        debug_logger.debug(f"Processing message with LLM: {message}")
        # LLM processing code here
        response = "..."  # Your actual LLM call
        debug_logger.debug(f"LLM response: {response}")
        return response
    except Exception as e:
        error_logger.error(f"Error in LLM processing: {str(e)}", exc_info=True)
        raise 
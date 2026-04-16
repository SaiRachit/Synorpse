"""
ReasoningHandlers.py - Action handlers for the Reasoning Engine

Wraps existing SYNORPSE capabilities to work with the ReasoningEngine.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ReasoningHandlers:
    """
    Provides action handlers for the ReasoningEngine.
    Wraps existing async functions to match the expected interface.
    """
    
    def __init__(self, async_search, async_chatbot, async_image_gen, 
                 async_automation, file_creator, analyze_screen=None, 
                 document_reader=None, conversation_context=None, phonebook=None):
        """
        Initialize with existing system components.
        
        Args:
            async_search: AsyncSearchWrapper instance
            async_chatbot: AsyncChatBot instance
            async_image_gen: AsyncImageGenerator instance
            async_automation: AsyncAutomation instance
            file_creator: FileCreator instance
            analyze_screen: Screen reader callable (optional)
            document_reader: DocumentQA instance (optional)
            conversation_context: ConversationContext for active file (optional)
            phonebook: WhatsApp phonebook dict (optional)
        """
        self.search = async_search
        self.chatbot = async_chatbot
        self.image_gen = async_image_gen
        self.automation = async_automation
        self.file_creator = file_creator
        self.analyze_screen = analyze_screen
        self.document_reader = document_reader
        self.conversation_context = conversation_context
        self.phonebook = phonebook or {}
    
    async def handle_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle web search action"""
        query = params.get("query", "")
        
        if not query:
            return {"success": False, "message": "No search query provided"}
        
        try:
            logger.info(f"ReasoningEngine: Searching for '{query}'")
            result = await self.search.search(query)
            
            # Truncate if too long
            if len(result) > 2000:
                result = result[:2000] + "\n... (truncated)"
            
            return {
                "success": True,
                "message": result
            }
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"success": False, "message": f"Search failed: {str(e)}"}
    
    async def handle_knowledge(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle knowledge query using search-backed AI (replaces chatbot)"""
        question = params.get("question", "")
        
        if not question:
            return {"success": False, "message": "No question provided"}
        
        try:
            from RealTimeSearchEngine import knowledge_query
            logger.info(f"ReasoningEngine: Knowledge query '{question}'")
            result = await knowledge_query(question)
            
            return {
                "success": True,
                "message": result
            }
        except Exception as e:
            logger.error(f"Knowledge query failed: {e}")
            return {"success": False, "message": f"Knowledge query failed: {str(e)}"}
    
    async def handle_create_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file creation"""
        file_type = params.get("file_type", "word")
        topic = params.get("topic", "Untitled")
        
        try:
            from pathlib import Path
            
            # Generate safe filename
            safe_name = "".join(c for c in topic[:30] if c.isalnum() or c in (' ', '_', '-')).strip()
            safe_name = safe_name.replace(' ', '_')
            base_path = Path.home() / "Documents" / safe_name
            
            logger.info(f"ReasoningEngine: Creating {file_type} file about '{topic}'")
            
            if file_type in ["python", "py"]:
                result = await self.file_creator.create_python_file(str(base_path), topic)
            elif file_type in ["word", "doc", "docx"]:
                result = await self.file_creator.create_word_file(str(base_path), topic, use_web=True)
            elif file_type == "pdf":
                result = await self.file_creator.create_pdf_file(str(base_path), topic, use_web=True)
            else:
                result = await self.file_creator.create_text_file(str(base_path), topic, use_web=True)
            
            return result
            
        except Exception as e:
            logger.error(f"File creation failed: {e}")
            return {"success": False, "message": f"File creation failed: {str(e)}"}
    
    async def handle_send_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle sending a message via WhatsApp or Email"""
        recipient = params.get("recipient", "")
        message = params.get("message", "")
        method = params.get("method", "whatsapp").lower()
        
        if not recipient:
            return {"success": False, "message": "No recipient provided"}
        
        try:
            if method == "email":
                logger.info(f"ReasoningEngine: Sending email to {recipient}")
                await self.automation.execute([f"email {recipient} {message}"])
                return {"success": True, "message": f"Email sent to {recipient}"}
            else:
                logger.info(f"ReasoningEngine: Sending WhatsApp to {recipient}")
                await self.automation.execute([f"whatsapp {recipient} {message}"])
                return {"success": True, "message": f"WhatsApp sent to {recipient}"}
                
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            return {"success": False, "message": f"Send failed: {str(e)}"}
    
    async def handle_open_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle opening an application"""
        app_name = params.get("app_name", "")
        
        if not app_name:
            return {"success": False, "message": "No app name provided"}
        
        try:
            logger.info(f"ReasoningEngine: Opening {app_name}")
            await self.automation.execute([f"open {app_name}"])
            return {"success": True, "message": f"Opened {app_name}"}
        except Exception as e:
            logger.error(f"Open app failed: {e}")
            return {"success": False, "message": f"Failed to open {app_name}: {str(e)}"}
    
    async def handle_generate_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle AI image generation"""
        prompt = params.get("prompt", "")
        
        if not prompt:
            return {"success": False, "message": "No image prompt provided"}
        
        try:
            logger.info(f"ReasoningEngine: Generating image '{prompt}'")
            image, seed, enhanced_prompt = await self.image_gen.generate(prompt)
            
            # Save the image
            image_id = await self.image_gen.save_to_db(image, prompt, enhanced_prompt, seed)
            image_path = await self.image_gen.save_to_file(image, prompt, seed)
            
            # Try to show
            try:
                image.show()
            except:
                pass
            
            return {
                "success": True,
                "message": f"Generated image (ID: {image_id}, Seed: {seed})",
                "path": str(image_path) if image_path else None
            }
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"success": False, "message": f"Image generation failed: {str(e)}"}
    
    async def handle_read_screen(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle screen reading/analysis action"""
        if not self.analyze_screen:
            return {"success": False, "message": "Screen reader not available"}
        
        query = params.get("query", "")
        try:
            logger.info(f"ReasoningEngine: Analyzing screen with query '{query}'")
            result = await self.analyze_screen(query)
            
            # The result is often JSON string from analyze_screen
            import json as _json
            try:
                parsed = _json.loads(result)
                if isinstance(parsed, dict) and "analysis" in parsed:
                    result = parsed["analysis"]
            except:
                pass
                
            return {
                "success": True,
                "message": result
            }
        except Exception as e:
            logger.error(f"Screen reading failed: {e}")
            return {"success": False, "message": f"Screen reading failed: {str(e)}"}

    async def handle_read_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reading/querying the active or specified document"""
        query = params.get("query", "summarize this document")
        
        try:
            # Try to get active file from conversation context
            active_file = None
            if self.conversation_context and hasattr(self.conversation_context, 'get_active_file'):
                active_file = self.conversation_context.get_active_file()
            
            if not active_file and not self.document_reader:
                return {"success": False, "message": "No document is currently active. Please upload a document first."}
            
            if not self.document_reader:
                # Create a fresh reader if not provided
                from DocumentReader import DocumentReader
                self.document_reader = DocumentReader()
            
            if active_file:
                logger.info(f"ReasoningEngine: Reading document '{active_file}' with query '{query}'")
                # Read the document if not already loaded
                if not self.document_reader.document_text:
                    self.document_reader.read_document(active_file)
                
                # Ask the question
                answer = self.document_reader.ask_question(query)
                return {"success": True, "message": answer}
            else:
                return {"success": False, "message": "No active document found. Upload a document first."}
                
        except Exception as e:
            logger.error(f"Document reading failed: {e}")
            return {"success": False, "message": f"Document reading failed: {str(e)}"}

    async def handle_finish(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle finishing the reasoning task"""
        answer = params.get("answer", "Task completed.")
        return {"success": True, "message": answer}
    
    def get_handlers_dict(self) -> Dict[str, Any]:
        """Get dictionary of all handlers for ReasoningEngine"""
        return {
            "search": self.handle_search,
            "search_knowledge": self.handle_knowledge,
            "chat": self.handle_knowledge,  # backward compat alias
            "create_file": self.handle_create_file,
            "send_message": self.handle_send_message,
            "open_app": self.handle_open_app,
            "generate_image": self.handle_generate_image,
            "read_screen": self.handle_read_screen,
            "read_document": self.handle_read_document,
            "finish": self.handle_finish
        }


# Global instance
_reasoning_handlers = None


def get_reasoning_handlers(async_search=None, async_chatbot=None, 
                           async_image_gen=None, async_automation=None,
                           file_creator=None, analyze_screen=None, 
                           document_reader=None, conversation_context=None,
                           phonebook=None):
    """Get or create global ReasoningHandlers instance"""
    global _reasoning_handlers
    if _reasoning_handlers is None and async_search:
        _reasoning_handlers = ReasoningHandlers(
            async_search, async_chatbot, async_image_gen,
            async_automation, file_creator, analyze_screen, 
            document_reader, conversation_context, phonebook
        )
    return _reasoning_handlers

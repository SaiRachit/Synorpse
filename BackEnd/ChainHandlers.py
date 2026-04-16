"""
Command Chain Handlers - Wrappers for existing commands to work with CommandChain
Converts existing async functions to work with chain context
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChainHandlers:
    """
    Handlers that wrap existing functionality for command chaining
    """
    
    def __init__(self, file_creator, automation, async_chatbot, async_search, async_image_gen, conversation_context, phonebook):
        """Initialize with existing system components"""
        self.file_creator = file_creator
        self.automation = automation
        self.chatbot = async_chatbot
        self.search = async_search
        self.image_gen = async_image_gen
        self.conversation_context = conversation_context
        self.phonebook = phonebook
    
    async def handle_create_file(self, params: Dict[str, Any], context) -> Dict[str, Any]:
        """
        Handle file creation step
        
        Args:
            params: {file_type, topic, content, use_conversation}
            context: ChainContext object
        
        Returns:
            Result dict with success, message, path
        """
        try:
            file_type = params.get("file_type", "word")
            # Use context.topic if available (from previous search), otherwise use params topic
            topic = context.topic if context.topic else params.get("topic", "Untitled")
            use_conversation = params.get("use_conversation", False)
            content = params.get("content")  # Pre-provided content
            
            # Generate default path
            safe_filename = "".join(c for c in topic[:30] if c.isalnum() or c in (' ', '_', '-')).strip()
            safe_filename = safe_filename.replace(' ', '_')
            default_path = Path.home() / "Documents" / f"{safe_filename}"
            
            logger.info(f"Creating {file_type} file: {topic}")
            
            # Use conversation context if requested
            if use_conversation:
                conv_turns = []
                if hasattr(self.conversation_context, 'get_recent_turns'):
                    conv_turns = self.conversation_context.get_recent_turns(5)
                else:
                    conv_turns = context.conversation_history
                
                result = await self.file_creator.create_from_conversation(
                    str(default_path), file_type, conv_turns, topic
                )
            
            # Use provided content
            elif content:
                # Create file with provided content
                if file_type == "python":
                    result = await self.file_creator.create_python_file(str(default_path), content)
                else:
                    # For documents, use search results as the topic to research
                    if file_type in ["word", "doc", "docx"]:
                        # If content looks like search results, use the original topic from context
                        actual_topic = context.topic if context.topic else topic
                        result = await self.file_creator.create_word_file(str(default_path), actual_topic, use_web=True)
                    elif file_type == "pdf":
                        actual_topic = context.topic if context.topic else topic
                        result = await self.file_creator.create_pdf_file(str(default_path), actual_topic, use_web=True)
                    else:
                        result = await self.file_creator.create_text_file(str(default_path), content, use_web=False)
            
            # Generate new content
            else:
                if file_type in ["python", "py"]:
                    result = await self.file_creator.create_python_file(str(default_path), topic)
                elif file_type in ["word", "doc", "docx"]:
                    result = await self.file_creator.create_word_file(str(default_path), topic, use_web=True)
                elif file_type == "pdf":
                    result = await self.file_creator.create_pdf_file(str(default_path), topic, use_web=True)
                elif file_type in ["text", "txt", "markdown", "md"]:
                    result = await self.file_creator.create_text_file(str(default_path), topic, use_web=True)
                else:
                    result = await self.file_creator.create_word_file(str(default_path), topic, use_web=True)
            
            return result
            
        except Exception as e:
            logger.error(f"File creation failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to create file: {str(e)}",
                "path": None
            }
    
    async def handle_send_whatsapp(self, params: Dict[str, Any], context) -> str:
        """
        Handle WhatsApp send step
        
        Args:
            params: {recipient, message, file_path (optional)}
            context: ChainContext object
        
        Returns:
            Result message string
        """
        try:
            recipient = params.get("recipient", "")
            message = params.get("message", "")
            file_path = params.get("file_path")
            
            # If no message provided, generate default
            if not message:
                if file_path:
                    message = f"Here's the file: {os.path.basename(file_path)}"
                else:
                    message = "Sent from SYNORPSE"
            
            # Import WhatsApp integration
            from WhatsappIntegration import send_whatsapp_desktop
            
            # Build query for send_whatsapp_desktop
            query = f"Send message to {recipient} saying {message}"
            
            logger.info(f"Sending WhatsApp message to {recipient}")
            success = send_whatsapp_desktop(query, self.phonebook, file_path=file_path)
            
            if success:
                return f"Sent WhatsApp message to {recipient}"
            else:
                return f"Failed to send WhatsApp message to {recipient}"
                
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}", exc_info=True)
            return f"Failed to send WhatsApp: {str(e)}"
    
    async def handle_send_email(self, params: Dict[str, Any], context) -> str:
        """Handle email send step"""
        try:
            recipient = params.get("recipient", "")
            subject = params.get("subject", "")
            message = params.get("message", "")
            file_path = params.get("file_path")
            
            # Import email integration
            from Automation import SendEmail
            
            # Best approach: use the original user query directly since SendEmail
            # has its own AI-powered extraction that understands full context.
            # Only fall back to param-based reconstruction if no original query.
            if hasattr(context, 'original_query') and context.original_query:
                query = context.original_query
            else:
                # Fallback: reconstruct from params
                parts = [f"Send email to {recipient}"]
                if subject:
                    parts.append(f"subject {subject}")
                if message:
                    parts.append(f"with message {message}")
                elif params.get("topic"):
                    parts.append(f"about {params['topic']}")
                query = " ".join(parts)
            
            logger.info(f"Sending email to {recipient}")
            import asyncio
            success = await asyncio.to_thread(SendEmail, query)
            
            if success:
                return f"Sent email to {recipient}"
            else:
                return f"Failed to send email to {recipient}"
            
        except Exception as e:
            logger.error(f"Email send failed: {e}", exc_info=True)
            return f"Failed to send email: {str(e)}"
    
    async def handle_search_web(self, params: Dict[str, Any], context) -> str:
        """Handle web search step"""
        try:
            # AI provides 'topic' parameter, but also support 'query' for backwards compatibility
            query = params.get("topic") or params.get("query", "")
            
            logger.info(f"Searching web for: {query}")
            results = await self.search.search(query)
            
            # Store the search topic in context for file creation
            context.set_topic(query)
            
            return str(results)
            
        except Exception as e:
            logger.error(f"Web search failed: {e}", exc_info=True)
            return f"Search failed: {str(e)}"
    
    async def handle_generate_image(self, params: Dict[str, Any], context) -> Dict[str, Any]:
        """Handle image generation step"""
        try:
            prompt = params.get("prompt", "")
            
            logger.info(f"Generating image: {prompt}")
            image, seed, enhanced_prompt = await self.image_gen.generate(prompt)
            
            # Save image
            image_id = await self.image_gen.save_to_db(image, prompt, enhanced_prompt, seed)
            image_path = await self.image_gen.save_to_file(image, prompt, seed)
            
            # Try to show image
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
            logger.error(f"Image generation failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to generate image: {str(e)}",
                "path": None
            }
    
    async def handle_chat(self, params: Dict[str, Any], context) -> str:
        """Handle chat/conversation step"""
        try:
            query = params.get("query", "")
            
            logger.info(f"Chat query: {query}")
            response = await self.chatbot.query(query)
            
            return str(response)
            
        except Exception as e:
            logger.error(f"Chat failed: {e}", exc_info=True)
            return f"Chat failed: {str(e)}"
    
    async def handle_open_app(self, params: Dict[str, Any], context) -> str:
        """Handle app/file opening step"""
        try:
            from Automation import Open
            
            # Check if we should open latest file from context
            if params.get("use_latest_file") and context.file_paths:
                file_path = context.get_latest_file()
                logger.info(f"Opening file: {file_path}")
                Open(file_path)
                return f"Opened {os.path.basename(file_path)}"
            else:
                query = params.get("query", "")
                logger.info(f"Opening: {query}")
                Open(query)
                return f"Opened {query}"
            
        except Exception as e:
            logger.error(f"Open failed: {e}", exc_info=True)
            return f"Failed to open: {str(e)}"
    
    async def handle_read_screen(self, params: Dict[str, Any], context) -> str:
        """Handle screen reading step"""
        try:
            question = params.get("question", "")
            logger.info(f"Reading screen: {question}")
            
            from ScreenReader import analyze_screen
            result = await analyze_screen(question)
            return result
            
        except Exception as e:
            logger.error(f"Screen reading failed: {e}", exc_info=True)
            return f"Failed to read screen: {str(e)}"
    
    def get_handlers_dict(self) -> Dict[str, Any]:
        """Get dictionary of all handlers for CommandChainExecutor"""
        return {
            "create_file": self.handle_create_file,
            "send_whatsapp": self.handle_send_whatsapp,
            "send_email": self.handle_send_email,
            "search_web": self.handle_search_web,
            "generate_image": self.handle_generate_image,
            "chat": self.handle_chat,
            "open_app": self.handle_open_app,
            "read_screen": self.handle_read_screen
        }


# Global instance
_chain_handlers = None


def get_chain_handlers(file_creator=None, automation=None, async_chatbot=None, 
                       async_search=None, async_image_gen=None, 
                       conversation_context=None, phonebook=None):
    """Get or create global ChainHandlers instance"""
    global _chain_handlers
    if _chain_handlers is None and file_creator:
        _chain_handlers = ChainHandlers(
            file_creator, automation, async_chatbot, async_search,
            async_image_gen, conversation_context, phonebook
        )
    return _chain_handlers

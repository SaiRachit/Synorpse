"""
Workflow Templates - Pre-defined patterns for common command chains
Provides templates and helpers for frequently used workflows
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class WorkflowTemplate:
    """Template for a common workflow pattern"""
    name: str
    description: str
    pattern: str
    steps: List[Dict[str, Any]]
    example: str


class WorkflowTemplates:
    """
    Collection of pre-defined workflow templates
    """
    
    # Template: Create file and send via messaging
    CREATE_AND_SEND = WorkflowTemplate(
        name="CREATE_AND_SEND",
        description="Create a file and send it via WhatsApp or Email",
        pattern=r"(create|make).*\band\b.*(send|share|whatsapp|email)",
        steps=[
            {
                "step_type": "create_file",
                "description": "Create file with specified content",
                "parameters": {"file_type": "auto", "topic": "extracted"},
                "depends_on_previous": False
            },
            {
                "step_type": "send_whatsapp",  # or send_email
                "description": "Send created file to recipient",
                "parameters": {"recipient": "extracted"},
                "depends_on_previous": True
            }
        ],
        example="Create a Python file with fibonacci code and send it to John on WhatsApp"
    )
    
    # Template: Search and document
    SEARCH_AND_DOCUMENT = WorkflowTemplate(
        name="SEARCH_AND_DOCUMENT",
        description="Search web and create document with findings",
        pattern=r"(search|find|look up).*\band\b.*(create|make|document|write)",
        steps=[
            {
                "step_type": "search_web",
                "description": "Search for information",
                "parameters": {"query": "extracted"},
                "depends_on_previous": False
            },
            {
                "step_type": "create_file",
                "description": "Create document with search results",
                "parameters": {"file_type": "word", "use_search_results": True},
                "depends_on_previous": True
            }
        ],
        example="Search for AI trends and create a Word document on this"
    )
    
    # Template: Generate and share
    GENERATE_AND_SHARE = WorkflowTemplate(
        name="GENERATE_AND_SHARE",
        description="Generate image and send to recipient",
        pattern=r"(generate|create).*image.*\band\b.*(send|share|whatsapp|email)",
        steps=[
            {
                "step_type": "generate_image",
                "description": "Generate image from prompt",
                "parameters": {"prompt": "extracted"},
                "depends_on_previous": False
            },
            {
                "step_type": "send_whatsapp",
                "description": "Send generated image",
                "parameters": {"recipient": "extracted"},
                "depends_on_previous": True
            }
        ],
        example="Generate an image of a sunset and send it to myself on WhatsApp"
    )
    
    # Template: Conversation to document
    CONVERSATION_TO_DOCUMENT = WorkflowTemplate(
        name="CONVERSATION_TO_DOCUMENT",
        description="Create document from current conversation context",
        pattern=r"(create|make).*(document|word|pdf).*\b(on this|about this|current topic)",
        steps=[
            {
                "step_type": "create_file",
                "description": "Create document from conversation",
                "parameters": {"file_type": "word", "use_conversation": True},
                "depends_on_previous": False
            }
        ],
        example="Create a Word document on this topic we've been discussing"
    )
    
    # Template: Multi-search and compare
    MULTI_SEARCH_AND_COMPARE = WorkflowTemplate(
        name="MULTI_SEARCH_AND_COMPARE",
        description="Search multiple sources and create comparison document",
        pattern=r"(compare|contrast).*\band\b.*(create|document|write)",
        steps=[
            {
                "step_type": "search_web",
                "description": "Search first topic",
                "parameters": {"query": "extracted_1"},
                "depends_on_previous": False
            },
            {
                "step_type": "search_web",
                "description": "Search second topic",
                "parameters": {"query": "extracted_2"},
                "depends_on_previous": False
            },
            {
                "step_type": "create_file",
                "description": "Create comparison document",
                "parameters": {"file_type": "word", "use_search_results": True},
                "depends_on_previous": True
            }
        ],
        example="Compare Python vs JavaScript and create a document"
    )
    
    # Template: File operations chain
    FILE_OPERATIONS_CHAIN = WorkflowTemplate(
        name="FILE_OPERATIONS_CHAIN",
        description="Create file, open it, and share it",
        pattern=r"(create).*\band\b.*(open).*\band\b.*(send|share)",
        steps=[
            {
                "step_type": "create_file",
                "description": "Create file",
                "parameters": {"file_type": "auto", "topic": "extracted"},
                "depends_on_previous": False
            },
            {
                "step_type": "open_app",
                "description": "Open created file",
                "parameters": {"use_latest_file": True},
                "depends_on_previous": True
            },
            {
                "step_type": "send_whatsapp",
                "description": "Send file",
                "parameters": {"recipient": "extracted"},
                "depends_on_previous": True
            }
        ],
        example="Create a presentation on AI, open it, and send to my team on WhatsApp"
    )
    
    @classmethod
    def get_all_templates(cls) -> List[WorkflowTemplate]:
        """Get all available workflow templates"""
        return [
            cls.CREATE_AND_SEND,
            cls.SEARCH_AND_DOCUMENT,
            cls.GENERATE_AND_SHARE,
            cls.CONVERSATION_TO_DOCUMENT,
            cls.MULTI_SEARCH_AND_COMPARE,
            cls.FILE_OPERATIONS_CHAIN
        ]
    
    @classmethod
    def get_template_by_name(cls, name: str) -> Optional[WorkflowTemplate]:
        """Get a specific template by name"""
        templates = {
            "CREATE_AND_SEND": cls.CREATE_AND_SEND,
            "SEARCH_AND_DOCUMENT": cls.SEARCH_AND_DOCUMENT,
            "GENERATE_AND_SHARE": cls.GENERATE_AND_SHARE,
            "CONVERSATION_TO_DOCUMENT": cls.CONVERSATION_TO_DOCUMENT,
            "MULTI_SEARCH_AND_COMPARE": cls.MULTI_SEARCH_AND_COMPARE,
            "FILE_OPERATIONS_CHAIN": cls.FILE_OPERATIONS_CHAIN
        }
        return templates.get(name.upper())
    
    @classmethod
    def get_examples(cls) -> List[str]:
        """Get example commands for all templates"""
        return [template.example for template in cls.get_all_templates()]


# Workflow pattern matchers
def detect_workflow_pattern(query: str) -> Optional[str]:
    """
    Detect which workflow pattern matches the query
    
    Args:
        query: User query
    
    Returns:
        Template name if matched, None otherwise
    """
    import re
    
    query_lower = query.lower()
    
    for template in WorkflowTemplates.get_all_templates():
        if re.search(template.pattern, query_lower):
            return template.name
    
    return None


# Context extraction helpers
def extract_file_type_from_query(query: str) -> str:
    """Extract file type from query (python, word, pdf, etc.)"""
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["python", ".py", "py file"]):
        return "python"
    elif any(word in query_lower for word in ["word", "doc", "docx", ".docx"]):
        return "word"
    elif any(word in query_lower for word in ["pdf", ".pdf"]):
        return "pdf"
    elif any(word in query_lower for word in ["text", "txt", ".txt"]):
        return "text"
    elif any(word in query_lower for word in ["markdown", "md", ".md"]):
        return "markdown"
    else:
        return "word"  # Default to Word


def extract_recipient_from_query(query: str) -> Optional[str]:
    """Extract recipient name from query"""
    import re
    
    # Look for "to X" or "send X"
    patterns = [
        r'(?:to|send\s+to)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
        r'(?:whatsapp|email)\s+(?:to\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            # Common self-references
            if recipient.lower() in ["myself", "me", "my"]:
                return "myself"
            return recipient
    
    return None


def extract_topic_from_query(query: str) -> Optional[str]:
    """Extract topic/subject from query"""
    import re
    
    # Remove common action words to isolate topic
    query_cleaned = query
    
    # Remove file type references
    query_cleaned = re.sub(r'\b(python|word|pdf|text|markdown|doc|docx)\s+(file|document)\b', '', query_cleaned, flags=re.IGNORECASE)
    
    # Remove action words
    query_cleaned = re.sub(r'\b(create|make|generate|write|send|share|whatsapp|email|and|to|on|about|with)\b', '', query_cleaned, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    query_cleaned = re.sub(r'\s+', ' ', query_cleaned).strip()
    
    return query_cleaned if query_cleaned else None


# Export helpers
__all__ = [
    'WorkflowTemplate',
    'WorkflowTemplates',
    'detect_workflow_pattern',
    'extract_file_type_from_query',
    'extract_recipient_from_query',
    'extract_topic_from_query'
]

"""
Pydantic data models for the Ticket Management system.

Defines the domain entities: Ticket, Comment, and KBArticle,
along with their creation/response schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TicketStatus(str, Enum):
    """Valid ticket statuses."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Valid ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketCategory(str, Enum):
    """Valid ticket categories."""
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Comment Models
# ---------------------------------------------------------------------------


class Comment(BaseModel):
    """A comment on a support ticket."""
    id: str = Field(..., description="Unique identifier (UUID v4)")
    ticket_id: str = Field(..., description="ID of the parent ticket")
    author: str = Field(..., description="Name or identifier of the comment author")
    content: str = Field(..., description="The comment text")
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")


class CommentCreate(BaseModel):
    """Schema for creating a new comment."""
    ticket_id: str = Field(..., description="ID of the ticket to comment on")
    author: str = Field(..., min_length=1, description="Comment author")
    content: str = Field(..., min_length=1, description="Comment text")


# ---------------------------------------------------------------------------
# Ticket Models
# ---------------------------------------------------------------------------


class Ticket(BaseModel):
    """A support ticket."""
    id: str = Field(..., description="Unique identifier (UUID v4)")
    title: str = Field(..., description="Brief summary of the issue")
    description: str = Field(..., description="Detailed description")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Current status")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Priority level")
    category: TicketCategory = Field(default=TicketCategory.OTHER, description="Ticket category")
    created_by: str = Field(..., description="Creator's identifier")
    assigned_to: Optional[str] = Field(default=None, description="Assignee's identifier")
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")
    updated_at: str = Field(..., description="ISO 8601 timestamp of last update")
    resolved_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of resolution")


class TicketCreate(BaseModel):
    """Schema for creating a new ticket."""
    title: str = Field(..., min_length=1, max_length=200, description="Brief summary (max 200 chars)")
    description: str = Field(..., min_length=1, description="Detailed description")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Priority level")
    category: TicketCategory = Field(default=TicketCategory.OTHER, description="Ticket category")
    created_by: str = Field(..., min_length=1, description="Creator's identifier")


class TicketWithComments(Ticket):
    """A ticket with its associated comments."""
    comments: list[Comment] = Field(default_factory=list, description="List of comments")


class TicketListResponse(BaseModel):
    """Response schema for listing tickets."""
    tickets: list[Ticket] = Field(default_factory=list)
    total_count: int = Field(..., description="Total number of matching tickets")


# ---------------------------------------------------------------------------
# Knowledge Base Models
# ---------------------------------------------------------------------------


class KBArticle(BaseModel):
    """A knowledge base article."""
    id: str = Field(..., description="Unique identifier (UUID v4)")
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Article body")
    category: str = Field(..., description="Article category")
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")


class KBSearchResult(BaseModel):
    """A single search result from the knowledge base."""
    id: str
    title: str
    content: str = Field(..., description="Article content (may be truncated)")
    category: str
    tags: Optional[str] = None
    relevance_score: float = Field(default=0.0, description="BM25 relevance score")


class KBSearchResponse(BaseModel):
    """Response schema for knowledge base search."""
    results: list[KBSearchResult] = Field(default_factory=list)
    total_results: int = Field(default=0)
    query: str = Field(..., description="The original search query")

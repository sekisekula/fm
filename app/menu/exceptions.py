"""
Custom exceptions for the Finance Manager Menu system.
"""

class FinanceManagerError(Exception):
    """Base exception for all Finance Manager menu related errors."""
    pass

class DatabaseError(FinanceManagerError):
    """Raised when there's an error with database operations."""
    pass

class UserInputError(FinanceManagerError):
    """Raised when there's an error with user input."""
    pass

class ReceiptProcessingError(FinanceManagerError):
    """Raised when there's an error processing a receipt."""
    pass

class ConfigurationError(FinanceManagerError):
    """Raised when there's a configuration error."""
    pass

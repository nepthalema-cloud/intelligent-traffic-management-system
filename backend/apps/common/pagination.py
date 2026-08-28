"""
Custom pagination classes for the AI-Powered Smart Traffic Management System.

Provides consistent pagination behaviour across all API endpoints.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    """
    Default pagination class for list endpoints.

    Clients may override the page size up to the configured maximum
    by passing ?page_size=<n> as a query parameter.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "example": 100},
                "total_pages": {"type": "integer", "example": 5},
                "current_page": {"type": "integer", "example": 1},
                "next": {"type": "string", "nullable": True, "format": "uri"},
                "previous": {"type": "string", "nullable": True, "format": "uri"},
                "results": schema,
            },
        }


class LargeResultsPagination(PageNumberPagination):
    """
    Pagination class for endpoints that may return larger result sets,
    such as bulk data exports or reporting endpoints.
    """

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
    page_query_param = "page"

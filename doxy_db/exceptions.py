class InvalidStatement(Exception):
    pass


class MalformedQuery(InvalidStatement):
    """Wrap sqlite3 execution errors with additional context."""

    pass


class IncompleteStatement(InvalidStatement):
    pass


class InvalidUsage(Exception):
    pass


class FrozenStatement(Exception):
    pass


class IncompatibleSchemaVersion(InvalidUsage):
    pass


class RequiredTypeMissing(InvalidUsage):
    pass


class RequiredRelationAtomMissing(InvalidUsage):
    pass


class RequiredRelationMissing(InvalidUsage):
    pass


class StatementArgumentMismatch(InvalidUsage):
    pass


class IncompatibleBaseQuery(InvalidUsage):
    def __init__(self, message, view, query_ob, results):
        message = "{}: {}".format(view.__class__.__name__, message)
        query_msg = "Query: {}".format(query_ob._full_query)
        results_msg = "Results: {}".format(results)
        super().__init__(message, query_msg, results_msg)

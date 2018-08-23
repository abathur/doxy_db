import copy
import sqlite3

from . import exceptions


class Silent(dict):
    def __missing__(self, _key):
        return ""


def quote(string):
    if string is None:
        return "?"
    return "'{}'".format(string)


class Statement(object):
    template = "{select}{from}{join}{where}{group_by}{order_by}{limit}"
    clauses = None
    _full_query = None
    _ids_only = None

    def __init__(self, api, base=None):
        self.api = api
        if base:
            self.clauses = copy.deepcopy(base.clauses)
        else:
            self.clauses = {"columns": "*"}

    def _select(self, clause):
        self.clauses["select"] = "SELECT {}".format(clause)
        return self

    def _from(self, clause):
        self.clauses["from"] = " FROM {}".format(clause)
        return self

    def _join(self, kind=None, conditions=None):
        if kind is None:
            self.clauses["join"] = " JOIN {}".format(conditions)
        # TODO: untested, unused; disabled for now
        # else:
        #     self.clauses["join"] = " {} JOIN {}".format(kind, conditions)
        return self

    def _where(self, clause):
        self.clauses["where"] = " WHERE {}".format(clause)
        return self

    # TODO: untested, unused; disabling until needed
    # def _group_by(self, clause):
    #     self.clauses["group_by"] = " GROUP BY {}".format(clause)
    #     return self

    def _order_by(self, clause):
        self.clauses["order_by"] = " ORDER BY {}".format(clause)
        return self

    def order_by(self, col, reverse=False):
        return self._order_by("{}{}".format(col, " DESC" if reverse else ""))

    def _limit(self, clause):
        self.clauses["limit"] = " LIMIT {}".format(clause)
        return self

    def limit(self, num):
        return self._limit(str(num))

    def table(self, name, id, columns=None):
        if columns is None:
            columns = []

        self.clauses["table"] = name
        table_col = "{}.{}".format(name, "{}")
        self.clauses["columns"] = [table_col.format(x) for x in columns]

        if id:
            # also generate an ID-only version
            self.clauses["id"] = "SELECT {}.{}".format(name, id)

        fmt = name + ".{}"
        self._select(
            ", ".join([fmt.format(col) for col in columns]) if columns else "*"
        )
        self._from(name)
        return self

    def where(self, *arg, **kwarg):
        """
        Compile arguments into the statement's where clause.

        Positional arguments are built in as-is (separated by AND), while kwargs are built into a keyword=value format.

        Caution: The string-quoting practice here is fine if we control the inputs, but it's not at all safe if the users control them. We do it here to support two goals:
        - support dynamically building tables or colnames into queries
        - support extending/branching/speciating queries without needing some really complex position-aware currying.

        We throw up a moderate hurdle by "freezing" the statement object on a call to prepare(), and disabling further modifications to it.

        Open to additional suggestions for keeping it from being a footgun.
        """

        if "where" in self.clauses:
            self.clauses["where"] = " AND ".join(
                [
                    self.clauses["where"],
                    *arg,
                    *["{}={}".format(k, quote(v)) for k, v in kwarg.items()],
                ]
            )
        else:
            self._where(
                " AND ".join(
                    [*arg, *["{}={}".format(k, quote(v)) for k, v in kwarg.items()]]
                )
            )

        return self

    def prepare(self):
        if "id" not in self.clauses or "table" not in self.clauses:
            raise exceptions.IncompleteStatement(
                "Set a table name and id via .table() before calling prepare."
            )

        self._full_query = self.template.format_map(Silent(self.clauses))
        self._ids_only = self.template.format_map(
            Silent(self.clauses, select=self.clauses["id"])
        )

        self._freeze()

        return self

    def _freeze(self):
        def frozen(*arg, **kwarg):
            raise exceptions.FrozenStatement(
                "To limit (but not eliminate) the risk of SQL injection, Statement objects are frozen when prepare() is called."
            )

        for prop in dir(self):
            if not prop.startswith("__") and callable(getattr(self, prop)):
                setattr(self, prop, frozen)

    def __call__(self, *args, ids_only=False):
        try:
            return self.api.connection.execute(
                self._ids_only if ids_only else self._full_query, tuple(args)
            )
        except sqlite3.OperationalError as e:
            raise exceptions.MalformedQuery(
                "Malformed query",
                self._ids_only if ids_only else self._full_query,
                tuple(args),
            ) from e
        except sqlite3.ProgrammingError as e:
            # Note: there may be more conditions that can raise this; it may need a broader message and exception type.
            raise exceptions.StatementArgumentMismatch(
                "Unexpected argument quantity",
                self._ids_only if ids_only else self._full_query,
                tuple(args),
            ) from e

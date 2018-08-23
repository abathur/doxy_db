from . import sql
from . import exceptions


class View(object):
    """
    Implements a query-driven view into the generated documentation.

    This class sets up some queries for different relations and such, but the basic rubric is to be lazy about these. Doxygen supports a *lot* of relations, some of which do and don't make sense under different circumstances.
    """

    root = None
    api = None

    _relation_queries = _find_queries = None

    def __init__(self, base):
        self.api = base.api
        self._relation_queries = {}
        self._find_queries = {}

        self.base_query = base.prepare()

        return

    def brief(self):
        raise NotImplementedError()

    # TODO: document pragmatic differences between structure and doc_structure (and maybe better distinguish these names?)
    def structure(self, **kwarg):
        raise NotImplementedError()

    def doc_structure(self):
        return self.list()

    def list(self, fields=None):
        """
        List

        Just uses the supplied base query (meaning it has weird semantics if the base query never returns more than 1 record)
        """
        raise NotImplementedError()

    def doc(self, fields=None):
        """
        Return document.

        Always uses base query.

        While the semantics of this are a bit weird for queries that return a list of results, it does use a different column set, so I'm not certain that it won't prove appropriate under some conditions.
        """
        result = self.base_query().fetchone()
        return result

    def _build_relation(
        self, alias, query, direction="child", relation=None, kinds=None
    ):
        """
        Construct and save a relationship query for later use.

        The alias, direction, and relation components come from the relationship atoms dictionary.

        The relationship query is based on the provided root query, which typically establishes the kind of records for which we're building a relationship.

        The (currently disabled) 'where' property enables further narrowing (in case a relation should be restricted to specific kinds or records). Also accompanied by a kwarg where=None
        """
        table = from_prefix = to_prefix = None

        # flip the relationship atom's prefixes based on direction.
        if direction == "child":
            name, table, from_prefix, to_prefix = self.api.atoms.get(relation)
        elif direction == "parent":
            name, table, to_prefix, from_prefix = self.api.atoms.get(relation)

        statement = (
            sql.Statement(self.api, query)
            ._select("[{alias}].*".format(alias=alias))
            ._from("def base")
            ._join(
                conditions="{table} as relative ON base.rowid=relative.{from_prefix}_rowid JOIN def [{alias}] ON [{alias}].rowid=relative.{to_prefix}_rowid".format(
                    alias=alias,
                    from_prefix=from_prefix,
                    to_prefix=to_prefix,
                    table=table,
                )
            )
        )
        if kinds:
            statement.where("[{}].kind in ('{}')".format(alias, "','".join(kinds)))

        # TODO: this was enabled, and could be supported, but I haven't found a use-case for it and thus can't make a non-trivial test to exercise it. Disabling but leaving in-place for now, in case real-world use makes the need obvious.
        # if where:
        #     statement.where(**where)

        self._relation_queries[alias] = statement.prepare()
        return statement

    def _relation(self, *arg, relation=None):
        # related(kind) queries are lazily constructed on first call using the root sql.Statement object, and adding relevant joins
        # 1. see if it's cached; call if so, try to build if not
        # 2. see if it's a known relation with predefined join names; actually build if so, raise error if not
        if relation not in self._relation_queries:
            rel = self.api.relations.get(relation)
            self._build_relation(
                rel[0], self.base_query, direction=rel[1], relation=rel[2], kinds=rel[3]
            )

        # this could fail, but I don't know how likely it is and I don't understand the conditions well enough to raise a sensible exception yet.
        return self._relation_queries[relation](*arg)

    def related(self, relations, *arg):
        return {x: self._relation(*arg, relation=x).fetchall() for x in relations}

    def doc_search(self, topic, tokens=None):
        """
        """
        match = self.find("name", topic)

        if match and tokens and len(tokens) and self._search_relation:
            return self.find_related(
                match[0].rowid, "name", tokens[0], relation=self._search_relation
            )

        return match

    def find_related(self, rowid, field, term, relation):
        # TODO: I think this is cacheable by relname+field, but I'm not sure if it's the same cache as the other location
        search = (
            sql.Statement(self.api, self._find_queries[relation.name])
            .where(**{"base.rowid": None, "{}.{}".format(relation.name, field): None})
            .prepare()
        )

        return search(rowid, term).fetchall()

    def find(self, field, term, relation=None):
        """
        Return records where field matches term, optionally searching across a relation.

        TODO: this might have errors or be open to a refactor now. I've made two big changes:
        - relation is typically a relation *object* and not a string name now (not sure I love this)
        - find_related() anchors search at an entity by refid

        In the wake of these, I have the suspicion that that this can either be further modularized, or perhaps that some of find() was made redundant.
        """

        # find piggybacks on on related, so
        # - see if we have a find query that matches
        # - if not, see if we have a relation query that does
        #     - if so, build a find query from it
        relname = relation.name if relation else None
        if relname not in self._find_queries:
            if relation is None:
                # this relation is special; base is root query
                self._find_queries[None] = self.base_query
            else:
                if relname in self._relation_queries:
                    self._find_queries[relname] = self._relation_queries[relname]
                else:
                    self._find_queries[relname] = self._build_relation(
                        relname,
                        self.base_query,
                        direction=relation.direction,
                        relation=relation.atom,
                        # TODO: where useful?
                    )

        # TODO: These entire searches are cacheable per relation+field, but not sure it's worth optimizing for now
        if relation:
            search = (
                sql.Statement(self.api, self._find_queries[relname])
                .where(**{"{}.{}".format(relname, field): None})
                .prepare()
            )
        else:
            search = (
                sql.Statement(self.api, self._find_queries[relname])
                .where(**{"{}".format(field): None})
                .prepare()
            )

        return search(term).fetchall()


class ListView(View):
    """
    View anchored on a list-returning query.
    """

    brief_description = None
    _search_relation = _search_query = None

    def __init__(self, base, brief_description, search_relation=None):
        super().__init__(base)

        result = base().fetchall()
        self.brief_description = brief_description

        if search_relation:
            self._search_relation = search_relation

            statement = self._build_relation(
                search_relation[0],
                base,
                direction=search_relation[1],
                relation=search_relation[2],
                kinds=search_relation[3],
            )
            self._find_queries[search_relation[0]] = self._search_query = statement

        if len(result):
            pass
        else:
            raise exceptions.IncompatibleBaseQuery(
                "base query matches no documents", self, base, result
            )

    def list(self):
        """
        List

        Just uses the supplied base query (meaning it has weird semantics if the base query never returns more than 1 record)
        """
        return self.base_query().fetchall()

    def structure(self, **kwarg):
        return self.api.types.get("section")(self.brief(), self.list(), "section", None)

    def brief(self):
        return self.brief_description


class DocView(View):
    """
    View anchored by (relative to) a defined entity (usually a compound).
    """

    _search_relation = _search_query = None

    def __init__(self, base, search_relation=None):
        super().__init__(base)

        result = base().fetchall()

        if search_relation:
            self._search_relation = search_relation

            statement = self._build_relation(
                search_relation[0],
                base,
                direction=search_relation[1],
                relation=search_relation[2],
                kinds=search_relation[3],
            )
            self._find_queries[None] = self._search_query = statement

        if len(result) > 1:
            raise exceptions.IncompatibleBaseQuery(
                "base query may not match more than one record.", self, base, result
            )
        elif len(result) == 1:
            self.root = result[0]
        else:
            raise exceptions.IncompatibleBaseQuery(
                "base query matches no documents", self, base, result
            )

    def list(self):
        """
        List

        Just uses the supplied base query (meaning it has weird semantics if the base query never returns more than 1 record)
        """
        return self._relation_queries[self._search_relation[0]]().fetchall()

    def structure(self, **kwarg):
        return self.api.types.get("section")(
            self.brief(), self.list(), "section", self.doc()
        )

    def brief(self):
        return self.doc().summary

    def find(self, field, term, relation=None):
        return super().find(field, term, relation=relation or self._search_relation)


class RelationView(DocView):
    """
    Special view, bound directly to the manual object, to provide some relational subqueries."""

    def __init__(self, base):
        View.__init__(self, base)

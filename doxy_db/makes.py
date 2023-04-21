"""
A number of defitions get re-used frequently; this module attempts to centralize and deduplicate them (a little; some of this still duplicates from Doxygen's source).

Not in love with how this works...
"""

from collections import namedtuple

from . import exceptions
from . import loggle

constants = namedtuple("constants", ("compound_kinds", "member_kinds", "relations"))

c = constants(
    compound_kinds={
        "category",
        "class",
        "dir",
        "enum",
        "example",
        "exception",
        "file",
        "group",
        "interface",
        "library",
        "module",
        "namespace",
        "package",
        "page",
        "protocol",
        "service",
        "singleton",
        "struct",
        "type",
        "union",
        "unknown",
        "",
    },
    member_kinds={
        "macro definition",
        "function",
        "variable",
        "typedef",
        "enumeration",
        "enumvalue",
        "signal",
        "slot",
        "friend",
        "dcop",
        "property",
        "event",
        "interface",
        "service",
    },
    relations={
        "reimplemented",
        "reimplements",
        "outercompounds",
        "innercompounds",
        "outerpages",
        "innerpages",
        "outerdirs",
        "innerdirs",
        "outerfiles",
        "innerfiles",
        "outerclasses",
        "innerclasses",
        "outernamespaces",
        "innernamespaces",
        "outergroups",
        "innergroups",
        "members",
        "compounds",
        "subclasses",
        "superclasses",
        "links_in",
        "links_out",
        "argument_links_in",
        "argument_links_out",
        "initializer_links_in",
        "initializer_links_out",
    },
)


class Defs(object):
    """Scaffold for type-specific singletons."""

    defs = None
    template = None

    def __init__(self):
        self.defs = {}
        self.extra_setup()

    def extra_setup(self):
        pass

    def on_missing(self, name, exception):
        raise NotImplementedError()

    def get(self, name):
        try:
            return self.defs[name]
        except KeyError as e:
            self.on_missing(name, e)

    def names(self):
        return self.defs.keys()

    def define(self, name, *arg):
        self.defs[name] = self.template(name, *arg)


class Types(Defs):
    """
    Scaffold for pre-defining our record types.

    The core purpose is defining namedtuples that will wrap rows returned from different sqlite3 queries.

    However, for consistency and clarity, we also use this same process to define a few types that this module uses to wrap its own returnables, including 'manuals', 'sections', and 'searches'.
    """

    cursor_type_cache = None

    def extra_setup(self):
        self.cursor_type_cache = {}

    def on_missing(self, name, exception):
        raise exceptions.RequiredTypeMissing("Required type not defined") from exception

    def cols(self, name):
        return self.get(name)._fields

    def define(self, name, fields):
        tupledef = []
        for column in fields:
            # This is the sqlite3/dbapi column descriptor format; we duplicate it so that we can use any given cursor's descriptor as a cache key.
            tupledef.append((column, None, None, None, None, None, None))

        typedef = namedtuple(name, fields)
        self.defs[tuple(tupledef)] = typedef
        self.defs[name] = typedef

    def _implicit(self, fields):
        typedef = namedtuple("_implicit", (x[0] for x in fields))
        self.defs[fields] = typedef
        return typedef

    def row_factory(self):
        def namedtuple_factory(cursor, row):
            """Returns sqlite rows as named tuples."""
            if cursor not in self.cursor_type_cache:
                try:
                    self.cursor_type_cache[cursor] = self.defs[cursor.description]
                except KeyError:
                    loggle.info(
                        "No pre-defined type found; generating implicit type for %s %s",
                        cursor,
                        row,
                    )

                    self.cursor_type_cache[cursor] = self._implicit(cursor.description)

            return self.cursor_type_cache[cursor](*row)

        return namedtuple_factory


def default_types():
    compound_cols = (
        "rowid",
        "kind",
        "name",
        "title",
        "file_id",
        "briefdescription",
        "detaileddescription",
    )
    member_cols = (
        "rowid",
        "name",
        "kind",
        "definition",
        "type",
        "argsstring",
        "scope",
        "inline",
        "bodystart",
        "bodyend",
        "bodyfile_id",
        "line",
        "detaileddescription",
        "briefdescription",
        "inbodydescription",
    )
    types = Types()
    types.define(
        "metadata",
        (
            "doxygen_version",
            "schema_version",
            "generated_at",
            "generated_on",
            "project_name",
            "project_number",
            "project_brief",
        ),
    )
    types.define("stub", ("rowid", "refid", "kind", "name", "summary"))

    types.define("compound", compound_cols)
    types.define("compound_rel", compound_cols + ("relations",))

    types.define("member", member_cols)
    types.define("member_rel", member_cols + ("relations",))

    types.define("section", ("summary", "children", "type", "root"))
    types.define("manual", ("root", "documents", "sections", "meta"))
    types.define("search", ("results",))

    # I want to limit noise here to types a consumer might want to leverage, so the system will implicitly create some internal-only types (like _relations and _distinct kinds) on first use.

    return types


class RelationAtoms(Defs):
    """
    Scaffold for pre-defining our relation atoms.

    Relation atoms are a way to help DRY up some code for handling a common Doxygen relationship-table pattern. A relation atom's tuple follows this format: (
      table_name,
      outside rowid prefix,
      inside rowid prefix,
    )

    The rowid foreign-key columns follow a format like <name>_rowid, so we just specify the unique part.

    This discussion continues at the Relations class, and goes into more detail at View._build_relation.
    """

    template = namedtuple(
        "relation_atom", ("name", "table", "parent_col_prefix", "child_col_prefix")
    )

    def on_missing(self, name, exception):
        raise exceptions.RequiredRelationAtomMissing(
            "Required relation atom '{}' not defined".format(name)
        ) from exception


def default_atoms():
    atoms = RelationAtoms()

    atoms.define("references", "inline_xrefs", "dst", "src")
    atoms.define("argument_references", "argument_xrefs", "dst", "src")
    atoms.define("initializer_references", "initializer_xrefs", "dst", "src")
    atoms.define("compounds", "contains", "outer", "inner")
    atoms.define("members", "member", "scope", "memberdef")
    atoms.define("inherits", "compoundref", "base", "derived")
    atoms.define("reimplementing", "reimplements", "memberdef", "reimplemented")

    return atoms


class Relations(Defs):
    """
    Scaffold for pre-defining our relations.

    Relations build on the relation atoms. The tuple format specifies: (
      the name of this relation on the originating object,
      child|parent (i.e., whether this relation points to the origin record's child, or parent),
      the relation atom to build from
    )

    Relation definitions come in parent/child pairs.

    For an example, let's say we've got two methods a::example() and b::example(), where b::example is a re-implementation of a::example.

    a::example will have a 'reimplemented' relation TOWARDS the parent/re-implementing b::example.
    b::example will have a 'reimplements' relation TOWARDS the child/re-implemented a::example.

    This discussion goes into more detail at View._build_relation.
    """

    defs = None
    template = namedtuple("relation", ("name", "direction", "atom", "kinds"))

    def __init__(self):
        self.defs = {}

    def on_missing(self, name, exception):
        raise exceptions.RequiredRelationMissing(
            "Required relation '{}' not defined".format(name)
        ) from exception


def default_relations():
    rels = Relations()

    # core Doxygen rels
    rels.define("reimplemented", "parent", "reimplementing", None)
    rels.define("reimplements", "child", "reimplementing", None)
    rels.define("outercompounds", "parent", "compounds", None)
    rels.define("innercompounds", "child", "compounds", None)
    rels.define("outerpages", "parent", "compounds", ("page",))
    rels.define("innerpages", "child", "compounds", ("page",))
    rels.define("outerdirs", "parent", "compounds", ("dir",))
    rels.define("innerdirs", "child", "compounds", ("dir",))
    rels.define("outerfiles", "parent", "compounds", ("file",))
    rels.define("innerfiles", "child", "compounds", ("file",))
    rels.define(
        "outerclasses",
        "parent",
        "compounds",
        (
            "category",
            "class",
            "enum",
            "exception",
            "interface",
            "module",
            "protocol",
            "service",
            "singleton",
            "struct",
            "type",
            "union",
        ),
    )
    rels.define(
        "innerclasses",
        "child",
        "compounds",
        (
            "category",
            "class",
            "enum",
            "exception",
            "interface",
            "module",
            "protocol",
            "service",
            "singleton",
            "struct",
            "type",
            "union",
        ),
    )
    rels.define("outernamespaces", "parent", "compounds", ("namespace",))
    rels.define("innernamespaces", "child", "compounds", ("namespace",))
    rels.define("outergroups", "parent", "compounds", ("group",))
    rels.define("innergroups", "child", "compounds", ("group",))
    rels.define("members", "child", "members", None)
    rels.define("compounds", "parent", "members", None)
    rels.define("subclasses", "child", "inherits", None)
    rels.define("superclasses", "parent", "inherits", None)
    rels.define("links_in", "child", "references", None)
    rels.define("links_out", "parent", "references", None)
    rels.define("argument_links_in", "child", "argument_references", None)
    rels.define("argument_links_out", "parent", "argument_references", None)
    rels.define("initializer_links_in", "child", "initializer_references", None)
    rels.define("initializer_links_out", "parent", "initializer_references", None)

    # Additional rels for common tasks
    rels.define("subpages", "child", "compounds", ("page",))
    rels.define("methods", "child", "members", ("function",))
    rels.define("properties", "child", "members", ("variable",))

    return rels


defaults = dict(
    type_factory=default_types,
    atom_factory=default_atoms,
    relation_factory=default_relations,
)

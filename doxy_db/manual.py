"""
Abstract SQL-backed doxygen manual API.

It is intended to sit at a fairly high abstraction level to encapsulate most of Doxygen's higher-level idioms. It tries to strike a balance between enabling consumers to perform common tasks without significant knowledge of Doxygen's internals, and providing a toolkit for using those idioms to extend a manual's behavior as needed.
"""
import re

from collections import namedtuple
from pkg_resources import parse_version


from . import db, sql, exceptions, loggle, DEFAULT_DB_URI


SUPPORTED_SCHEMA_VERSION = parse_version("0.2.0")
FIRST_COMPAT_DOXYGEN_VERSION = parse_version("1.8.15")


def default_tokenizer(search_string):
    return re.split(r"\s", search_string)


def create(uri, description=None, **kwarg):
    return Manual(uri, description, **kwarg).extend(add_manual_api)


def add_manual_api(api):
    api.page_tree = api.make_compound_tree(["page"], api.relations.get("subpages"))
    api.class_doc = api.make_compound_tree(["class"], api.relations.get("methods"))
    api.struct_doc = api.make_compound_tree(["struct"], api.relations.get("methods"))

    try:
        api.indexpage = api.root_page("refid", "indexpage")
    except exceptions.IncompatibleBaseQuery as e:
        loggle.warning(
            "No indexpage found; falling back on generic pre-generated index document.",
            exc_info=e,
        )

    return api


def doxygen_manual(manual):
    # TODO: goal was to by default use Doxygen's manual structure, roughly:
    # - pages nested under innerpages of the indexpage
    # - non-nested pages loose in the root
    # - sections for classes, modules, files, members
    #
    # That said, this looks trickier than I thought, so it might be better to fall back on something that is clear and simple, rather than try to get close but have a lot of asterisks or need to complicate the code.
    manual.mount(None, manual.topmost(["page"], "Super brief description"))
    manual.mount(
        "modules",
        manual.kinds(
            ["group"],
            "Super brief description",
            search_relation=manual.relations.get("methods"),
        ),
    )
    manual.mount(
        "classes",
        manual.kinds(
            ["class"],
            "Super brief description",
            search_relation=manual.relations.get("methods"),
        ),
    )
    # TODO: "files" is complex because it combines dirs and files; holding off on it
    # The outer level should in theory always be a directory, but markdown pages kinda screw everything up here in the sense that they all get DOCUMENTED AS FILES but then they DON'T EVER GET DOCUMENTED AS INNERFILE. This is understandable, because it's kinda "right" that these not show up as files. They show up as pages. The *problem* is that I can't run a naive search for files+directories that have no outerdir (I wouldn't expect any files to actually match this query--but it would be nice if I could use it as the base). Instead, many markdown pages match this query, because they aren't actually documented in any given directory.

    return manual


class Manual(db.DoxygenSQLite3):
    root = sections = documents = description = _meta = None

    def __init__(self, uri, description, tokenizer=default_tokenizer, **kwarg):
        # section = (name, sectob, section.doc_structure())
        self.sections = []
        # document = namedtuple stub(...)
        self.documents = []
        self.description = description
        self.tokenizer = tokenizer

        no_meta_table = False

        super().__init__(uri, **kwarg)
        try:
            self._meta = sql.Statement(self).table("meta", "id").prepare()().fetchone()
        except exceptions.MalformedQuery:
            no_meta_table = True

        if no_meta_table or "schema_version" not in self._meta._fields:
            raise exceptions.IncompatibleSchemaVersion(
                "This database was either not generated by Doxygen, or it was generated before the schema was versioned. It will not work with {our_name}. The first Doxygen version that produces a compatible database (schema {support_schema}) is {first_compat_doxygen}.".format(
                    our_name="doxygen_manual",
                    support_schema=SUPPORTED_SCHEMA_VERSION,
                    first_compat_doxygen=FIRST_COMPAT_DOXYGEN_VERSION,
                )
            )
        # TODO: We could make a less strict version that could support minor updates, but I think this is probably asking for trouble until the dust settles, no? (1.0?)
        elif parse_version(self._meta.schema_version) != SUPPORTED_SCHEMA_VERSION:
            raise exceptions.IncompatibleSchemaVersion(
                "This version of {our_name} ({our_version}) is compatible with version {support_schema} of the Doxygen Sqlite3 schema, but this database uses schema version {db_schema} (generated by Doxygen {db_doxygen}). You may want to use a different version of this module or Doxygen.".format(
                    our_name="doxygen_manual",
                    our_version="0.0",
                    support_schema=SUPPORTED_SCHEMA_VERSION,
                    db_schema=self._meta.schema_version,
                    db_doxygen=self._meta.doxygen_version,
                )
            )

    def tokenize(self, command):
        return self.tokenizer(command)

    def meta(self):
        return self._meta

    def brief(self):
        """
        Short manual description.

        Tries 4 things in order:
        - override description passed to the manual constructor
        - the project_brief from the doxygen conf
        - the brief of the indexpage, if any
        - a generic fallback string
        """
        return (
            self.description
            or self._meta.project_brief
            or self.root.title
            or "Doxygen-generated manual"
        )

    def doc_search(self, query, tokens=None):
        """

        Return formats for this are a bit of an open question.
        """

        # Below just returns empty. This means the user's responsible for what to do after an empty search. Right format?
        if not query:
            return []

        if not tokens:
            tokens = self.tokenize(query)

        target = tokens.pop(0)

        results = []

        # if any sections match the target, pass the full query if there are unhandled tokens, or just return the section root/doc if not
        for name, section, _subsection in self.sections:
            if target == name:  # lowercase?
                if len(tokens):
                    target = tokens.pop(0)
                    results = section.doc_search(target, tokens=tokens)
                else:
                    # TODO: is this the right format?
                    return [section.structure()]

        # Otherwise, try searching my local documents for the target
        if not results or not len(results):
            results = self.query(target, self.documents)

        # Fall back; see if <target> exists in any section
        if not results or not len(results):
            results = []
            for _name, section, _subsections in self.sections:
                result = section.doc_search(target, tokens)

                if result and len(result):
                    results.extend(result)

        return results

    def query(self, topic, within):
        """
        """
        partial_matches = []
        for doc in within:
            # try for an exact match
            if doc.name == topic:
                return [doc]
            elif doc.name.find(topic) > -1:
                partial_matches.append(doc)

        return partial_matches or None

    def doc_fetch(self, rowid):
        # KISS for now:
        # search compounddef for rowid
        # search memberdef if no compounddef
        # append relations

        # Start query prep work
        compound_cols = self.types.cols("compound")
        compound_rel = namedtuple("compound_rel", compound_cols + ("relations",))

        member_cols = self.types.cols("member")
        member_rel = namedtuple("member_rel", member_cols + ("relations",))

        compound = (
            sql.Statement(self)
            .table("compounddef", id="rowid", columns=compound_cols)
            .where(rowid=None)
            .prepare()
        )

        member = (
            sql.Statement(self)
            .table("memberdef", id="rowid", columns=member_cols)
            .where(rowid=None)
            .prepare()
        )

        # joins rel table for relation infoz
        rel = sql.Statement(self).table("rel", "rowid").where(rowid=None).prepare()

        # TODO: this probably benefits nicely from caching. A simple query against this (select count(*) from (select distinct reimplemented,reimplements,innercompounds,outercompounds,innerpages,outerpages,innerdirs,outerdirs,innerfiles,outerfiles,innerclasses,outerclasses,innernamespaces,outernamespaces,innergroups,outergroups,members,compounds,subclasses,superclasses,links_in,links_out,argument_links_in,argument_links_out,initializer_links_in,initializer_links_out from rel);) revealed that my test databases with 214 and 1834 defs had only 35 and 33 distinct relation combinations. FWIW, it might be possible to cache this on the SQL side, but since sqlite doesn't have an array type, we'd still have to intentionally convert it here.
        relations = [
            k for k, v in rel(rowid).fetchone()._asdict().items() if v and k != "rowid"
        ]
        # end query prep

        found = compound(rowid).fetchone()
        if not found:
            found = member(rowid).fetchone()
            found = member_rel(**found._asdict(), relations=relations)
        else:
            found = compound_rel(**found._asdict(), relations=relations)

        return found

    def doc_related(self, rowid, relations):
        return self.relview.related(relations, rowid)

    def doc_structure(self):
        # a document could also be a section; knocking out any docs that appear in sections
        docs = {
            x for x in self.documents if x not in [y[1].root for y in self.sections]
        }

        return self.types.get("manual")(
            self.root, docs, [x[1].structure() for x in self.sections], self._meta
        )

    def mount(self, name, section, root=None):
        # if the thing we're mounting declares a root document, it can't be *my* root document
        if section.root and section.root == self.root:
            raise exceptions.InvalidUsage(
                "Can't mount a section with the same root document as the current manual."
            )

        if hasattr(section, "publish"):
            section.publish(root=root or section.root or None)

        if name:
            self.sections.append((name, section, section.doc_structure()))
        else:
            self.documents.extend(section.doc_structure())

    def publish(self, root=None):
        # preload the root document
        if root:
            self.root = self.root_page("name", root).root
        elif self.indexpage:
            self.root = self.indexpage.root
        else:
            pass
            # rootless manual. We could 'fake' a document here if this poses real problems, but it's probably more useful to leave this up to the user/interface than generate something useless.


# TODO: document and promote this pattern. Basically, it's ideal if consumer modules don't auto-publish their manuals in their global scopes. This enables someone to import and mount their manual elsewhere. Not going to try to enforce it, of course.
def default_doxygen_manual(uri=DEFAULT_DB_URI, root=None):
    man = create(uri).compile(doxygen_manual)
    man.publish(root=root)
    return man

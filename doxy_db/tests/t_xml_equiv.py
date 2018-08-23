"""
Establishes equivalence baseline between the XML output on one hand, and the view into the documentation supported by the doxygen_sqlite3 database via our Statement and View objects.

Note: This could of course be compiled down into explicit SQL statements *just* for comparing the XML and SQL outputs. I don't see this as highly meaningful for this doxygen_db python project--tests for that level of equivalence are probably best done in doxygen's core testset, to ensure that gaps aren't opening up between the XML and SQL outputs. I'm not sure if Python is appropriate for those tests, and building a robust XML <-> SQLite test is probably beyond my scope and limited C++ knowledge.
"""

import unittest
import itertools
import xml.etree.ElementTree as ET

from .. import db as doxygen_db
from .. import views
from .. import sql
from ..makes import c
from . import TEST_DB, TEST_XML


db = doxygen_db.DoxygenSQLite3(TEST_DB)
xml = ET.parse(TEST_XML)

sql_compound_kinds = {
    x.kind
    for x in db.connection.execute("select distinct kind from compounddef;").fetchall()
}
xml_compound_kinds = {x.get("kind") for x in xml.findall(".//compounddef")}


# XML and this module use different kind strings (this manual hews to the actual strings; XML shortens these), so we need to translate sql -> xml
def translate(kind):
    if kind == "macro definition":
        return "define"
    elif kind == "enumeration":
        return "enum"

    return kind


sql_member_kinds = {
    x.kind
    for x in db.connection.execute("select distinct kind from memberdef;").fetchall()
}
xml_member_kinds = {x.get("kind") for x in xml.findall(".//memberdef")}

xml_translated_sql_member_kinds = set(map(translate, sql_member_kinds))


all_sql_kinds = {*sql_compound_kinds, *sql_member_kinds}

sql_members = [
    el
    for el in xml.findall(".//memberdef")
    if el.get("kind") in xml_translated_sql_member_kinds
]
sql_compounds = [
    el for el in xml.findall(".//compounddef") if el.get("kind") in sql_compound_kinds
]

biggo_list = sql_members + sql_compounds

xml_entity_rowids = [x.get("id") for x in biggo_list]

# map out partial selectors from db relation -> relevant XML node
xml_rel = {
    "reimplemented": "reimplementedby",
    "reimplements": "reimplements",
    "innercompounds": "inner*",
    "outercompounds": "inner*/..",
    "innerpages": "innerpage",
    "outerpages": "innerpage/..[@kind='page']",
    "innerdirs": "innerdir",
    "outerdirs": "innerdir/..",
    "innerfiles": "innerfile",
    "outerfiles": "innerfile/..[@kind='file']",
    "innerclasses": "innerclass",
    "outerclasses": "innerclass/..[@kind='class']",
    "innernamespaces": "innernamespace",
    "outernamespaces": "innernamespace/..[@kind='namespace']",
    "innergroups": "innergroup",
    "outergroups": "innergroup/..",
    "members": "/member",
    "compounds": "/member/../..",
    "subclasses": "derivedcompoundref",
    "superclasses": "basecompoundref",
    "links_in": "referencedby",
    "links_out": "references",
    "argument_links_in": "param/type/..",
    "argument_links_out": "param/type/..",
    # TODO: below probably aren't right; I don't have a docset that has any to test against
    "initializer_links_in": "initializer/ref/../..",
    "initializer_links_out": "initializer/ref",
}


class TestMeta(unittest.TestCase):
    """These tests include hand-maintained lists of some entities in the codebase. It seems prudent to have some meta-tests that ensure these don't fall out of sync."""

    def test_test_relations_in_sync(self):
        self.assertEqual(set(xml_rel.keys()), c.relations)


class TestAssumptions(unittest.TestCase):
    """
    Attempt to encode assumptions the code makes about the structure of the generated documentation.

    I probably should have started this process a little earlier; it is probably missing some useful tests. The idea is to have a place to codify such leaps.

    The test docset I develop against is a little small, and it would be good to know when assumptions drawn from this small set fall apart on a larger one.
    """

    def test_can_discard_innerX_name(self):
        """
        Assumption: innerX node text is available elsewhere (thus, it doesn't need to be saved).

        We were saving the text in nodes like <innerclass...>name</innerclass>, but it *looks* like this information is available from the referred-to entity's compoundname/title fields

        Note: The 'name' field may also need to be added on a larger docset; not certain.
        """
        mismatches = []
        for x in [
            "innerpage",
            "innerclass",
            "innergroup",
            "innerfile",
            "innerdir",
            "innernamespace",
        ]:
            for match in xml.findall(".//{}".format(x)):

                names = [
                    x.text
                    for x in xml.findall(
                        ".//*[@id='{}']/*".format(match.attrib["refid"])
                    )
                    if x.tag in ("compoundname", "title")
                ]

                if match.text not in names:
                    mismatches.append(
                        dict(
                            refid=match.attrib["refid"],
                            innerXtext=match.text,
                            compoundNames=names,
                            innerX=x,
                        )
                    )

        self.assertEqual(mismatches, [])

    def test_innerX_contents_documented(self):
        """
        Assumption: entities appearing within innerX will also have a corresponding memberdef/compounddef. The sqlite3 generator only needs to use them to document the inner/outer relation (even if it hasn't seen the memberdef/compounddef yet).
        """
        xml_refids = {x.get("id") for x in xml.findall(".//*[@id]")}
        xml_innerX_refids = {
            x.get("refid")
            for x in xml.findall(".//*[@refid]")
            if x.tag.startswith("inner")
        }
        self.assertTrue(xml_innerX_refids.issubset(xml_refids))

    @unittest.skipUnless(
        xml.find(".//*[@ambiguityscope]"),
        "No nodes with an ambiguityscope found to check against.",
    )
    def test_member_ambiguityscope_equals_memberdef_scope(self):
        """
        Assumption: recording the ambiguityscope is wasteful in our case, because it *appears* to always match the memberdef's scope.

        (It might be worthwhile if we were further denormalized, but we aren't far enough denormalized for it to be useful.)
        """
        for i, ambig in enumerate(xml.findall(".//*[@ambiguityscope]")):
            runs = i

            for memberdef in xml.findall(
                ".//memberdef[@id='{}']".format(ambig.get("refid"))
            ):
                guess = ambig.get("ambiguityscope") + memberdef.findtext("name")
                self.assertTrue(memberdef.findtext("definition").endswith(guess))


class TestEntities(unittest.TestCase):
    locs = xml.findall(".//location")
    files = set(filter(None, map(lambda x: x.get("file", None), locs)))
    bodyfiles = set(filter(None, map(lambda x: x.get("bodyfile", None), locs)))

    def test_all_files_accounted_for(self):
        """
        Note: This used to test all SQL files, but it looks like SQL is tracking the special bug/deprecated/test/todo-list pages as files, but no entities will list those as their file/bodyfile. I'm not sure we're "wrong" to track these files, so for now I'm knocking out the special page types before comparing.
        """

        def badfile(path):
            for bad in ("bug", "deprecated", "test", "todo"):
                if path.endswith(bad):
                    return True
            return False

        xml_files = self.files.union(self.bodyfiles)
        sql_files = {
            x.name
            for x in db.connection.execute("select distinct name from file;")
            if not badfile(x.name)
        }

        self.assertEqual(xml_files, sql_files)

    def test_file_associations(self):
        """
        Ideal: check all locations in XML, and all IDs on memberdef/compounddef in SQL.

        Reality: XML doesn't give example, page, or group compounds a location, so we have to exclude from SQL query.
        """
        for file in self.files:
            # both memberdef and compounddef
            xml_entities = {
                x.get("id")
                for x in xml.findall(".//location[@file='{}']/..".format(file))
            }
            sql_memberdefs = {
                x.refid
                for x in db.connection.execute(
                    "select distinct refid from refid join memberdef on refid.rowid=memberdef.rowid join file on memberdef.file_id=file.rowid where file.name=?;",
                    (file,),
                )
            }
            sql_compounddefs = {
                x.refid
                for x in db.connection.execute(
                    "select distinct refid from refid join compounddef on refid.rowid=compounddef.rowid join file on compounddef.file_id=file.rowid where file.name=? and compounddef.kind not in ('page', 'example', 'group');",
                    (file,),
                )
            }
            sql_entities = sql_memberdefs.union(sql_compounddefs)

            self.assertEqual(
                xml_entities,
                sql_entities,
                msg="mismatch between entities associated with file '{}'".format(file),
            )

    def test_all_members_accounted_for(self):
        """
        For a while we were attempting to build up member->compound relations via membernameinfo iterators, which I think is roughly analogous to listofallmembers.

        Unfortunately, this only worked for class compounds. Now, all memberdefs are associated with their scopes. This ensures they're all in the database.

        Caveats:
        - We aren't handling enums yet, so I'm intentionally excluding them here.
        """
        enumvalue_refids = {x.get("id") for x in xml.findall(".//enumvalue")}
        xml_links = set()
        for compound in xml.findall(".//listofallmembers/member/../.."):
            scope = compound.get("id")
            for member in compound.findall(".//member"):
                refid = member.get("refid")
                if refid not in enumvalue_refids:
                    xml_links.add((scope, refid))

        sql_links = set(
            db.connection.execute(
                "select scope.refid as scope_refid,memberdef.refid as memberdef_refid from member join refid scope on member.scope_rowid=scope.rowid join refid memberdef on member.memberdef_rowid=memberdef.rowid;"
            ).fetchall()
        )

        # we actually just want to make sure all of xml is in sql.
        self.assertEqual(xml_links.difference(sql_links), set())


class TestMemberdef(unittest.TestCase):
    def test_all_def_refids_accounted_for(self):
        xml_refids = {x.get("id") for x in xml.findall(".//memberdef")}
        sql_refids = {
            x.refid
            for x in db.connection.execute(
                "select distinct refid from refid join memberdef on refid.rowid=memberdef.rowid;"
            )
        }

        self.assertEqual(xml_refids, sql_refids)

    def _gen(kind, in_sql=False, in_xml=False):
        if in_sql:

            def func(self):
                sql_kind = kind
                xml_kind = translate(kind)
                member_sql = {
                    member.refid
                    for member in db.kinds([sql_kind], "brief description").list()
                }

                # Cheating a bit here. XML can have multiple memberdefs if there are separate declarations and definitions; sql deduplicates this. Below generates a set, and sorted implicitly converts back into list.
                # Note: If we ever need to distinguish, probably easier to do it somewhere where we already need to run an XML search for this refid, where we could easily handle single and double memberdefs differently.
                member_xml = {
                    member.get("id")
                    for member in xml.findall(
                        ".//memberdef[@kind='{}']".format(xml_kind)
                    )
                }

                self.assertEqual(member_sql, member_xml)

                # NOTE: if we wanted to keep drilling down...
                # for refid in members_sql:
                # 	with self.subTest(refid=refid):
                # 		self.validate_member(refid)

            return func
        elif in_xml:

            def func(self):
                raise unittest.SkipTest(
                    "memberdef kind: '{}' not yet supported by sqlite3gen".format(kind)
                )

            return func
        else:

            def func(self):
                raise unittest.SkipTest(
                    "memberdef kind: '{}' missing from tested docset (or unsupported by xmlgen)".format(
                        kind
                    )
                )

            return func

    ns = locals()

    for kind in c.member_kinds:
        test_name = "test_{}_rowids".format(kind)
        if kind in sql_member_kinds:
            ns[test_name] = _gen(kind, in_sql=True, in_xml=True)
        elif kind in xml_member_kinds:
            ns[test_name] = _gen(kind, in_sql=False, in_xml=True)
        else:
            ns[test_name] = _gen(kind, in_sql=False, in_xml=False)

            # If some need special care, override via: def test_{kind}_rowids(self):...


class TestCompounddef(unittest.TestCase):
    def test_all_def_refids_accounted_for(self):
        xml_refids = {x.get("id") for x in xml.findall(".//compounddef")}
        sql_refids = {
            x.refid
            for x in db.connection.execute(
                "select distinct refid from refid join compounddef on refid.rowid=compounddef.rowid;"
            )
        }

        self.assertEqual(xml_refids, sql_refids)

    def _gen(kind, in_sql=False, in_xml=False):
        if in_sql:

            def func(self):
                sql_kind = xml_kind = kind
                compound_sql = sorted(
                    [
                        compound.refid
                        for compound in db.kinds([sql_kind], "brief description").list()
                    ]
                )

                compound_xml = sorted(
                    {
                        compound.get("id")
                        for compound in xml.findall(
                            "./compounddef[@kind='{}']".format(xml_kind)
                        )
                    }
                )

                self.assertEqual(compound_sql, compound_xml)

                # for refid in compound_sql:
                # 	with self.subTest(refid=refid):
                # 		self.validate_compound(refid)

            return func
        elif in_xml:

            def func(self):
                raise unittest.SkipTest(
                    "compounddef kind: '{}' not yet supported by sqlite3gen".format(
                        kind
                    )
                )

            return func
        else:

            def func(self):
                raise unittest.SkipTest(
                    "compounddef kind: '{}' missing from tested docset (or unsupported by xmlgen)".format(
                        kind
                    )
                )

            return func

    ns = locals()

    for kind in c.compound_kinds:
        test_name = "test_{}_rowids".format(kind)
        if kind in sql_compound_kinds:
            ns[test_name] = _gen(kind, in_sql=True, in_xml=True)
        elif kind in xml_compound_kinds:
            ns[test_name] = _gen(kind, in_sql=False, in_xml=True)
        else:
            ns[test_name] = _gen(kind, in_sql=False, in_xml=False)


class TestRelations(unittest.TestCase):
    # we want to run the same basic gut-check that compounddef does; query SQL for all of these relations and note which have any matches; do the same in XML

    relquery = "select {} from rel;".format(
        ", ".join(["MAX([{rel}]) as [{rel}]".format(rel=x) for x in c.relations])
    )

    sql_rels = [
        rel
        for rel, val in db.connection.execute(relquery).fetchone()._asdict().items()
        if val
    ]

    sql_view = views.RelationView(
        sql.Statement(db, db._def)
        ._select("*")
        ._from("def base")
        ._where("base.kind in {}".format(tuple(all_sql_kinds)))
    )
    sql = sql_view.related(sql_rels)

    def _gen(relation, in_sql=False, in_xml=False):
        if in_sql:

            def func(self):
                # get a big list of Element objects for both compounddef and memberdef, keep only kinds in our SQL list, and then run the additional queries by mapping them against this list

                related_xml = set(
                    itertools.chain.from_iterable(
                        filter(
                            None,
                            [
                                el.findall("./{}".format(xml_rel[relation]))
                                for el in biggo_list
                            ],
                        )
                    )
                )

                xml_rowids = set([x.get("refid") or x.get("id") for x in related_xml])

                related_sql = set([related.refid for related in self.sql[relation]])

                if not related_sql.issuperset(
                    xml_rowids.intersection(xml_entity_rowids)
                ):
                    raise Exception(
                        relation,
                        xml_rel[relation],
                        self.sql[relation],
                        related_sql,
                        xml_rowids.intersection(xml_entity_rowids),
                    )

                self.assertTrue(
                    related_sql.issuperset(xml_rowids.intersection(xml_entity_rowids))
                    # Cheating. SQL is ends up with a handful of enum-member refids (via <member> tags), but it isn't handling the requisite enum definitions, because they *aren't* compounddefs. So I'm making a global map of compound+memberdef refids, and intersecting to knock any enumvalues out here. This probably only really matters for <member>.
                    # TODO: There might be a better/less-hacky solution (but I'd rather just put that effort into eventually handling correctly)
                )

            return func
        elif in_xml:

            def func(self):
                raise unittest.SkipTest(
                    "relation: {} mis-queried by this module or not yet supported by sqlite3gen".format(
                        relation
                    )
                )

            return func
        else:

            def func(self):
                raise unittest.SkipTest(
                    "relation: {} missing from tested docset (or unsupported by xmlgen)".format(
                        relation
                    )
                )

            return func

    ns = locals()

    for relation in c.relations:
        test_name = "test_{}_rowids".format(relation)
        if relation in sql_rels:
            ns[test_name] = _gen(relation, in_sql=True, in_xml=True)
        elif xml.find(".//{}".format(xml_rel[relation])):
            ns[test_name] = _gen(relation, in_sql=False, in_xml=True)
        else:
            ns[test_name] = _gen(relation, in_sql=False, in_xml=False)

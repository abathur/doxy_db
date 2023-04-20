"""
The Manual class sits at a fairly high abstraction layer, and draws on multiple lower-layers. This introduces more room for misuse.

Two main threads to exercising the manual API are:
- ensure that objects when used in a nonsensical way
- confirm that the abstract interface it provides returns what our intuition expects
"""

import unittest
import os

from .. import manual
from .. import exceptions

import xml.etree.ElementTree as ET
from . import TEST_DB, TEST_XML, EMPTY_DB, PREVIOUS_DB

xml = ET.parse(TEST_XML)


def make_manual():
    # build a strange manual that can exercise everything
    man = manual.create(TEST_DB, "test manual 1").compile(manual.doxygen_manual)
    man2 = manual.create(TEST_DB, "test manual 2").compile(manual.doxygen_manual)

    man.mount("blah", man2, root="mypage1")
    man.mount("ah", man.class_doc(name="Example_Test"))
    man.mount("bah", man.class_doc(refid="classB"))
    man.mount(None, man.topmost(["page"], "So many pages"))
    man.mount("modules", man.kinds(["group"], "list of groups"))
    man.mount(
        "structs",
        man.kinds(
            ["struct"], "list of structs", search_relation=man.relations.get("methods")
        ),
    )
    man.mount(
        "classes",
        man.kinds(
            ["class"], "list of classes", search_relation=man.relations.get("methods")
        ),
    )
    man.mount("functions", man.kinds(["function"], "list of functions"))
    man.ambiguous = man.make_compound_tree(
        ["namespace", "class"], man.relations.get("methods")
    )
    man.publish()
    return man


def make_empty():
    return manual.default_doxygen_manual(uri=EMPTY_DB)


def make_previous():
    return manual.default_doxygen_manual(uri=PREVIOUS_DB)


man = make_manual()

# TODO: should eventually be a test ensuring this query either returns nothing, or doesn't return anything that isn't an expected failure? (enums match for now...)
# select refid from refids where rowid not in (select rowid from ref);


# This could test the view factories explicitly, but I'm going to hold off until I have any evidence that an implicit test via composed views is insufficient.
class TestViews(unittest.TestCase):
    # == view factories ==

    # tests topmost, implicitly ListView
    def test_topmost(self):
        x = man.topmost(["class"], "class tree")
        # ListView: get, list, structure, brief
        # View: find, related, doc, doc_structure
        result = set([x.refid for x in x.doc_structure()])
        # all classes
        top_classes = set(
            [x.get("id") for x in xml.findall(".compounddef[@kind='class']")]
        )

        # classes that don't appear as an innerclass of another class
        but_no_innerclasses = top_classes.difference(
            set(
                [
                    x.get("refid")
                    for x in xml.findall(".//compounddef[@kind='class']/innerclass")
                ]
            )
        )

        self.assertSetEqual(result, but_no_innerclasses)

    # tests page_tree, implicitly DocView?
    def test_page_tree(self):
        with self.assertRaises(exceptions.InvalidUsage):
            man.page_tree(invalid="argument")

    # == composed views ==

    # implicitly tests root_page, DocView
    def test_indexpage(self):
        # TODO: the stock example directory doesn't have an indexpage. Chalk that up as another reason I need to make my own test docset (or add to Doxygen's examples) for this, but for now I'll just test that it raises the appropriate error.
        with self.assertRaises(exceptions.InvalidUsage):
            man.root_page("refid", "indexpage")

    # RelationView is atypical. It only exists to support manual.doc_related, so for now it's implicitly exercised via doc_related tests.
    # def test_relview(self):
    #     pass

    def test_brief(self):
        # What's the goal in testing this, and can I avoid a lot of scaffolding for something ultimately trivial? (i.e., there are multiple locations this could be looking for a brief, so the amount of code necessary to validate the correctness of every returned string seems pretty high relative to its value).
        #
        # For now:
        # 1. ensure all of these object types have brief methods and return a brief
        #
        # Maybe later:
        # 2. ensure submanuals and subsections exist to exercise all possible fallbacks (mostly just verifying that none of them throw errors)
        # 3. actually validate all possible returns
        for name, ob, _subsects in man.sections:
            self.assertIsInstance(ob.brief(), str)

    def test_compounds(self):
        """
        Ensure the manual interface and XML output yield the same list of class refids.

        This is a higher-level version of tests in test_xml_equivalence. TODO: If gaps do turn up between this test and those, it could test types much more extensively than it does.
        """
        classes_sql = man.kinds(["class"], "brief_description").list()

        classes_xml = sorted(
            [cls.get("id") for cls in xml.findall(".//compounddef[@kind='class']")]
        )

        self.assertEqual(sorted([cls.refid for cls in classes_sql]), classes_xml)

    # DocView can only resolve to one record
    def test_ambiguous_docview(self):
        with self.assertRaises(exceptions.IncompatibleBaseQuery):
            man.ambiguous(name="ns::oo_class")

    # ListView must resolve to at least one record
    def test_empty_listview(self):
        with self.assertRaises(exceptions.IncompatibleBaseQuery):
            man.kinds(["fake_kind"], "fake description")

    def test_find(self):
        vehicle = man.struct_doc(name="Vehicle")

        # vehicle has a Car subclass, but not a Car superclass
        self.assertTrue(
            len(vehicle.find("name", "Car", relation=man.relations.get("subclasses")))
        )
        self.assertFalse(
            len(vehicle.find("name", "Car", relation=man.relations.get("superclasses")))
        )

        # and an Object superclass, but not an Object subclass
        self.assertFalse(
            len(
                vehicle.find("name", "Object", relation=man.relations.get("subclasses"))
            )
        )
        self.assertTrue(
            len(
                vehicle.find(
                    "name", "Object", relation=man.relations.get("superclasses")
                )
            )
        )

        # it has a vehicleStart method
        self.assertTrue(
            len(
                vehicle.find(
                    "name", "vehicleStart", relation=man.relations.get("methods")
                )
            )
        )

        # it has a 'base' member, but 'base' is a variable--so it won't show up in methods
        self.assertFalse(
            len(vehicle.find("name", "base", relation=man.relations.get("methods")))
        )

    @unittest.skip(
        "This stopped working. Two newer examples, CMakeLists_8txt and page_8doc, match docview but not fileview."
    )
    def test_list(self):
        """
        This test may be worthless.

        The main non-trivial test I could think of, at the manual level, was setting up two views that have different list method definitions in such a way that they should still yield the same docsets.

        TODO: this test should be deleted, replaced, or rewritten. It's a tricky validation, and the existing version broke down over bad assumptions.
        """

        self.maxDiff = None

        # this should directly list all files
        listview = man.kinds(["file"], "test")

        # since we only have one directory, named examples, listing all of its innerfile children should give us all of our files...
        fileview = man.make_compound_tree(["dir"], man.relations.get("innerfiles"))
        docview = fileview(name="examples")

        self.assertEqual(docview.list(), listview.list())

    def test_members(self):
        """
        Ensure the manual interface and XML output yield the same list of class refids.

        This is a higher-level version of tests in test_xml_equivalence. If gaps do turn up between this test and those, it could test types much more extensively than it does.
        """
        define_sql = man.kinds(["macro definition"], "brief_description").list()

        define_xml = sorted(
            [mbd.get("id") for mbd in xml.findall(".//memberdef[@kind='define']")]
        )

        self.assertEqual(sorted([mbd.refid for mbd in define_sql]), define_xml)


class TestManual(unittest.TestCase):
    def test_meta(self):
        # TODO: this is a pretty meaningless test for coverage. I think it's worth revisiting with some notion of either schema versions or doxygen versions, since it's sane to insist on the client being appropriate for the generated database, and exceptions thrown by that feature would implicitly test the functioning of the meta table.
        results = man.meta()
        fields = results._fields
        self.assertIn("doxygen_version", fields)
        self.assertIn("schema_version", fields)
        self.assertIn("generated_at", fields)
        self.assertIn("generated_on", fields)
        self.assertIn("project_name", fields)
        self.assertIn("project_number", fields)
        self.assertIn("project_brief", fields)

    def test_bad_meta(self):
        with self.assertRaises(exceptions.IncompatibleSchemaVersion):
            make_empty()

    def test_outdated_meta(self):
        with self.assertRaises(exceptions.IncompatibleSchemaVersion):
            make_previous()

    def test_duplicate_root(self):
        with self.assertRaises(exceptions.InvalidUsage):
            # no reason to waste cycles; using simpler default manual, which auto-publishes
            man1 = manual.default_doxygen_manual(TEST_DB, "bug")
            man2 = manual.default_doxygen_manual(TEST_DB, "bug")
            man1.mount("bad", man2)

    def test_doc_search(self):
        # also tests query (implicitly) and doc_fetch
        stub = man.types.get("stub")
        compound_rel = man.types.get("compound_rel")
        member_rel = man.types.get("member_rel")

        # TODO: below smell kinda meaningless
        results = man.doc_search(None)
        self.assertEqual(results, list())

        results = man.doc_search("")
        self.assertEqual(results, list())

        bravenewman = make_manual()
        results = bravenewman.doc_search("missing_term")
        self.assertEqual(results, list())

        results = man.doc_search("functions member")
        self.assertEqual(
            set(results),
            set(
                [
                    stub(
                        rowid=8,
                        refid="classAfterdoc__Test_1a57ba94e9039ee90a1b191ae0009a05dd",
                        kind="function",
                        name="member",
                        summary="<para>a member function. </para>\n",
                    ),
                    stub(
                        rowid=15,
                        refid="classAutolink__Test_1a393ea281f235a2f603d98daf72b0d411",
                        kind="function",
                        name="member",
                        summary='<para><ref refid="classA" kindref="compound">A</ref> member function. </para>\n',
                    ),
                    stub(
                        rowid=16,
                        refid="classAutolink__Test_1acf783a43c2b4b6cc9dd2361784eca2e1",
                        kind="function",
                        name="member",
                        summary="<para>An overloaded member function. </para>\n",
                    ),
                    stub(
                        rowid=58,
                        refid="classFn__Test_1a823b5c9726bb8f6ece50e57ac8e3092c",
                        kind="function",
                        name="member",
                        summary='<para><ref refid="classA" kindref="compound">A</ref> member function. </para>\n',
                    ),
                ]
            ),
        )

        # TODO: multiple tests here use the "Example" page as a target, and I got a hint of why that might be a bad idea when someone changed its name from "example" to "pag_example", and I had to make 5 edits below. This is a broad problem with tests where I've pinned expected values. I haven't come up with a solution I prefer to copy-pasting, yet. Excluding the most-likely parts to meaninglessly shift is an optimization, but it's not like someone couldn't delete, rename, or re-describe any of these in any given commit.

        results = man.doc_search("example").pop()
        self.assertTupleEqual(
            results,
            stub(
                **{
                    "rowid": results.rowid,
                    "refid": "pag_example",
                    "kind": "page",
                    "name": "pag_example",
                    "summary": "",
                }
            ),
        )
        doc = man.doc_fetch(results.rowid)
        self.maxDiff = None

        self.assertTupleEqual(
            doc,
            compound_rel(
                rowid=doc.rowid,
                kind="page",
                name="pag_example",
                title="pag_example",
                file_id=doc.file_id,
                briefdescription="",
                detaileddescription='<para> Our main function starts like this: <programlisting filename="include_test.cpp"></programlisting>First we create an object <computeroutput>t</computeroutput> of the <ref refid="classInclude__Test" kindref="compound">Include_Test</ref> class. <programlisting filename="include_test.cpp"></programlisting>Then we call the example member function <programlisting filename="include_test.cpp"></programlisting>After that our little test routine ends. <programlisting filename="include_test.cpp"></programlisting></para>\n',
                relations=[],
            ),
        )
        self.assertIn(
            [x for x in man.doc_search("modules group5")][0],
            man.doc_search("modules")[0].children,
        )

        # TODO: this tests partial matching; this currently only works for *documents* at the manual level, and views don't support a similar concept. I *think* views should support this, but I'm holding off until a late pass in case I have some documented reason for excluding subsections from this fuzzy search?
        results = man.doc_search("examp").pop()
        self.assertTupleEqual(
            results,
            stub(
                **{
                    "rowid": 202,
                    "refid": "pag_example",
                    "kind": "page",
                    "name": "pag_example",
                    "summary": "",
                }
            ),
        )

        results = list(man.doc_search("ah example"))
        self.assertEqual(len(results), 1)

        doc = man.doc_fetch(results.pop().rowid)
        self.maxDiff = None

        self.assertEqual(
            doc,
            member_rel(
                rowid=doc.rowid,
                name="example",
                kind="function",
                definition="void Example_Test::example",
                type="void",
                argsstring="()",
                scope="Example_Test",
                inline=0,
                bodystart=14,
                bodyend=14,
                bodyfile_id=doc.bodyfile_id,
                line=11,
                detaileddescription="<para>More details about this function. </para>\n",
                briefdescription="<para>An example member function. </para>\n",
                inbodydescription="",
                relations=["compounds"],
            ),
        )

        # drilldown syntax
        self.assertEqual(
            man.doc_search("structs Truck vehicleStart"),
            [
                stub(
                    rowid=31,
                    refid="structVehicle_1a6891d3d28853bc3fdd075596dc6de9f8",
                    kind="function",
                    name="vehicleStart",
                    summary="",
                )
            ],
        )

        self.assertEqual(
            man.doc_search("modules group1 func"),
            [
                stub(
                    rowid=156,
                    refid="group__group1_1ga24f647174760cac13d2624b5ad74b00c",
                    kind="function",
                    name="func",
                    summary="<para>function in group 1 </para>\n",
                )
            ],
        )

    def test_doc_fake_relation(self):
        with self.assertRaises(exceptions.RequiredRelationMissing):
            man.doc_related(1, ["fake_relation"])

    def test_doc_related(self):
        compound = man.doc_fetch(man.doc_search("Vehicle").pop().rowid)
        comp_rels = man.doc_related(compound.rowid, compound.relations)

        subclass_names = {x.name for x in comp_rels["subclasses"]}
        superclass_names = {x.name for x in comp_rels["superclasses"]}
        argument_links_in_names = {x.name for x in comp_rels["argument_links_in"]}

        self.assertEqual(superclass_names, {"Object"})
        self.assertEqual(subclass_names, {"Car", "Truck"})
        self.assertEqual(argument_links_in_names, {"vehicleStart", "vehicleStop"})

        member = man.doc_fetch(man.doc_search("vehicleStart").pop().rowid)
        memb_rels = man.doc_related(member.rowid, member.relations)

        class_names = {x.name for x in memb_rels["compounds"]}
        self.assertEqual(class_names, {"Car", "Truck", "Vehicle"})

    # TODO: this name might be bad. It's not obvious if this tests something about the structure of a view, or tests a view method named structure, or what?
    def test_view_structure(self):
        docview = man.doc_search("ah").pop()
        self.assertEqual(docview.root.refid, "classExample__Test")
        self.assertEqual(
            docview.children,
            man.doc_related(docview.root.rowid, relations=["members"])["members"],
        )

        # TODO: make a more complex list-view section that supports some non-boring test here?
        # listview = man.doc_search("modules").pop()

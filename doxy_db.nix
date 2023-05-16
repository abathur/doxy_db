{ python311Packages
, doxygen
, runCommand
, libxslt
}:

# at nixpkgs 3913f6a514fa3eb29e34af744cc97d0b0f93c35c
# - python36, 37, and 38 all work
# - python39 fails on something in pyflakes
# at nixpkgs d1c3fea7ecbed758168787fe4e4a3157e52bc808 april 14 2022
# - python 38, 39, 310 work
# - python311 fails on something in cython
# at nixpkgs c2c0373ae7abf25b7d69b2df05d3ef8014459ea3 sept 15 2022
# - python311 works
# at nixpkgs 55070e598e0e03d1d116c49b9eff322ef07c6ac6 feb 12 2023
# - python311 works
# at nixpkgs 8ad5e8132c5dcf977e308e7bf5517cc6cc0bf7d8 mar 11 2023
let
  builtExamples = runCommand "built_examples" {
    # not really necessary for a package that's in stdenv
    DOXYGEN_ROOT = "${doxygen}";
    DOXYGEN_EXAMPLES_DIR = "${doxygen.examples}";
    nativeBuildInputs = [ libxslt doxygen ];
    examples = ./examples.conf;
  } ''
    doxygen $examples
    mkdir -p $out
    pushd xml
    # combine everything into the index
    xsltproc combine.xslt index.xml > $out/all.xml
    popd
    cp doxygen_sqlite3.db $out/doxygen_sqlite3.db
  '';
in python311Packages.buildPythonPackage rec {

  # now it's our turn
  pname = "doxy_db";
  version = "0.0.1";
  src = ./.;

  nativeCheckInputs = with python311Packages; [

  ] ++ [ lxml pytest pytestcov pytestrunner ];
  COLUMNS = 114; # override to tidy output
  preCheck = ''
    # check format
    # TODO: format has floated, but let's get this all on stable ground before catching up
    # black --check --target-version py36 *.py doxy_db

    mkdir -p doxy_db/tests/xml
    cp ${builtExamples}/all.xml doxy_db/tests/xml/all.xml
    cp ${builtExamples}/doxygen_sqlite3.db doxy_db/tests/doxygen_sqlite3.db
  '';
}

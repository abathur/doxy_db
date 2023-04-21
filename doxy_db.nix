{ python311Packages
, doxygen
, fetchFromGitHub
, sqlite
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
  # building my version of doxygen first
  doxygen_sqlite3 = doxygen.overrideAttrs (attrs: rec {
    name = "doxygen-1.9.6-sqlite3gen";
    # src = fetchFromGitHub {
    #   owner  = "abathur";
    #   repo   = "doxygen";
    #   # specific fix commit (now merged, unreleased)
    #   # Release_1_9_0, Release_1_9_1, Release_1_9_2, Release_1_9_3, Release_1_9_4, Release_1_9_5, Release_1_9_6
    #   # bad: b8a3ff6c33264c43cdf30c04baa9793e7e8d51a2 592aaa4f17d73ec8c475df0f44efaea8cc4d575c
    #   # good: 6a7201851a1667da40b4e2a1cf7b481c2d386803 5d0281a264e33ec3477bd7f6a9dcef79a6ef8eeb e03e2a29f9279deabe62d795b0db925a982d0eef
    #   rev    = "test_schema_version_fix_1_9_6";
    #   hash   = "sha256-C9UiMSZtEY0cbR0A7TYKyZU8gdYYgDuuW6aDL/bvG5g=";
    # };
    buildInputs = attrs.buildInputs ++ [ sqlite ];
    cmakeFlags = [
      "-Duse_sqlite3=ON"
    ] ++ attrs.cmakeFlags;
    postInstall = ''
      # put examples in output so doxy_db can test against them
      cp -r ../examples $examples
    '';
    outputs = [ "out" "examples" ];
  });

  builtExamples = runCommand "all.xml" {
    # not really necessary for a package that's in stdenv
    DOXYGEN_ROOT = "${doxygen_sqlite3}";
    DOXYGEN_EXAMPLES_DIR = "${doxygen_sqlite3.examples}";
    nativeBuildInputs = [ libxslt doxygen_sqlite3 ];
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
    # black --check --target-version py36 *.py doxy_db

    mkdir -p doxy_db/tests/xml
    cp ${builtExamples}/all.xml doxy_db/tests/xml/all.xml
    cp ${builtExamples}/doxygen_sqlite3.db doxy_db/tests/doxygen_sqlite3.db
  '';
}

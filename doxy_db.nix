{ python36Packages
, doxygen
, fetchFromGitHub
, sqlite
, libxslt
}:

python36Packages.buildPythonPackage rec {
  # building my version of doxygen first
  doxygen_sqlite3 = doxygen.overrideAttrs (attrs: rec {
    name = "doxygen-1.9.5-sqlite3gen";
    src = fetchFromGitHub {
      owner  = "abathur";
      repo   = "doxygen";
      # specific fix commit (now merged, unreleased)
      # Release_1_9_0, Release_1_9_1, Release_1_9_2, Release_1_9_3, Release_1_9_4, Release_1_9_5, Release_1_9_6
      # bad: b8a3ff6c33264c43cdf30c04baa9793e7e8d51a2 592aaa4f17d73ec8c475df0f44efaea8cc4d575c
      # good: 6a7201851a1667da40b4e2a1cf7b481c2d386803 5d0281a264e33ec3477bd7f6a9dcef79a6ef8eeb e03e2a29f9279deabe62d795b0db925a982d0eef
      rev    = "test_schema_version_fix_1_9_5";
      hash   = "sha256-n/MNXBk0oxx1Sflbhutn5zDM/PeKYrbfaWP8bYldZ3c=";
    };
    buildInputs = attrs.buildInputs ++ [ sqlite ];
    cmakeFlags = [
      "-Duse_sqlite3=ON"
    ] ++ attrs.cmakeFlags;
    postInstall = ''
      # put examples in output so doxy_db can test against them
      cp -r ../examples $out/examples
    '';
  });

  # now it's our turn
  pname = "doxy_db";
  version = "0.0.1";
  src = ./.;

  DOXYGEN_ROOT = "${doxygen_sqlite3}";
  DOXYGEN_EXAMPLES_DIR = "${doxygen_sqlite3}/examples";

  checkInputs = with python36Packages; [
    libxslt
    doxygen_sqlite3
  ] ++ [ lxml pytest pytestcov pytestrunner black ];
  COLUMNS = 114; # override to tidy output
  preCheck = ''
    # check format
    black --check --target-version py36 *.py doxy_db

    # build docs
    doxygen examples.conf

    # combine everything into the index
    pushd doxy_db/tests/xml
    xsltproc combine.xslt index.xml > all.xml
    popd
  '';

  # clean up? irrelevant on CI, but useful locally
  postCheck = ''
    rm -rf doxy_db/tests/xml doxy_db/tests/doxygen_sqlite3.db
  '';
}

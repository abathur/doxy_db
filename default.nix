{ pkgs ? import <nixpkgs> {} }:

pkgs.python36Packages.buildPythonPackage rec {
  # building my version of doxygen first
  doxygen = pkgs.doxygen.overrideAttrs (attrs: rec {
    name = "doxygen-1.8.19-sqlite3gen";
    src = pkgs.fetchFromGitHub {
      owner  = "doxygen";
      repo   = "doxygen";
      # specific fix commit (now merged, unreleased)
      rev    = "129bffd3885650cbf462c969d47bf74ee4e9ff06";
      sha256 = "01ci8s3kvhj10kxhyw6q333cssj00ava37ygyf9n0dgnkfrn6sih";
    };
    buildInputs = attrs.buildInputs ++ [ pkgs.sqlite ];
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

  DOXYGEN_ROOT = "${doxygen}";
  DOXYGEN_EXAMPLES_DIR = "${doxygen}/examples";

  checkInputs = with pkgs.python36Packages; [
    pkgs.libxslt
    doxygen
  ] ++ [ lxml pytest pytestcov pytestrunner black ];
  COLUMNS = 114; # override to tidy output
  preCheck = ''
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

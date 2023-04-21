{ doxygen
, fetchFromGitHub
, sqlite
}:

doxygen.overrideAttrs (attrs: rec {
  name = "doxygen-1.9.6-sqlite3gen";
  src = fetchFromGitHub {
    owner  = "abathur";
    repo   = "doxygen";
    # specific fix commit (now merged, unreleased)
    # Release_1_9_0, Release_1_9_1, Release_1_9_2, Release_1_9_3, Release_1_9_4, Release_1_9_5, Release_1_9_6
    # bad: b8a3ff6c33264c43cdf30c04baa9793e7e8d51a2 592aaa4f17d73ec8c475df0f44efaea8cc4d575c
    # good: 6a7201851a1667da40b4e2a1cf7b481c2d386803 5d0281a264e33ec3477bd7f6a9dcef79a6ef8eeb e03e2a29f9279deabe62d795b0db925a982d0eef
    rev    = "test_schema_version_fix_1_9_6";
    hash   = "sha256-C9UiMSZtEY0cbR0A7TYKyZU8gdYYgDuuW6aDL/bvG5g=";
  };
  buildInputs = attrs.buildInputs ++ [ sqlite ];
  cmakeFlags = [
    "-Duse_sqlite3=ON"
  ] ++ attrs.cmakeFlags;
  postInstall = ''
    # put examples in output so doxy_db can test against them
    cp -r ../examples $examples
  '';
  outputs = [ "out" "examples" ];
})

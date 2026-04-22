//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-PrePassLighting" {
Properties {

_LightTexture0 ("", any) = "" { }

_LightTextureB0 ("", 2D) = "" { }

_ShadowMapTexture ("", any) = "" { }

}
SubShader {
 Pass {
  Tags { "SHADOWSUPPORT" = "true" }
 ZWrite Off
  GpuProgramID 28712
}
 Pass {
  Tags { "SHADOWSUPPORT" = "true" }
 ZWrite Off
  GpuProgramID 130940
}
}
}
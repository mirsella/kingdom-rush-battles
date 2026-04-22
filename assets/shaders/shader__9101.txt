//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-UIRAtlasBlitCopy" {
Properties {

_MainTex0 ("Texture", any) = "" { }

_MainTex1 ("Texture", any) = "" { }

_MainTex2 ("Texture", any) = "" { }

_MainTex3 ("Texture", any) = "" { }

_MainTex4 ("Texture", any) = "" { }

_MainTex5 ("Texture", any) = "" { }

_MainTex6 ("Texture", any) = "" { }

_MainTex7 ("Texture", any) = "" { }

}
SubShader {
 Pass {
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 52704
}
}
}
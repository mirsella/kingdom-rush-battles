//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/BlitToDepth_MSAA" {
Properties {

_MainTex ("DepthTexture", any) = "" { }

}
SubShader {
 Pass {
 ZTest Always
 Cull Off
  GpuProgramID 5328
}
}
}
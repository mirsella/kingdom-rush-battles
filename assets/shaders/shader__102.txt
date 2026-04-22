//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-Flare" {
Properties {

}
SubShader {
 Tags { "RenderType" = "Overlay" }
 Pass {
  Tags { "RenderType" = "Overlay" }
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 9990
}
}
}
//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-DeferredReflections" {
Properties {

_SrcBlend ("", Float) = 1.0

_DstBlend ("", Float) = 1.0

}
SubShader {
 Pass {
 ZWrite Off
  GpuProgramID 19311
}
 Pass {
 ZTest Always
 ZWrite Off
  GpuProgramID 113442
}
}
}
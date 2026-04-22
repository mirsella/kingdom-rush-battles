//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/VideoDecodeAndroid" {
Properties {

}
SubShader {
 Pass {
 Name "RGBAExternal_To_RGBA"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 37716
}
 Pass {
 Name "RGBASplitExternal_To_RGBA"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 74759
}
}
}
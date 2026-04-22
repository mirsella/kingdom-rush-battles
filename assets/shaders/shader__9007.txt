//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-GUIRoundedRectWithColorPerBorder" {
Properties {

_MainTex ("Texture", any) = "white" { }

_SrcBlend ("SrcBlend", Float) = 5.0

_DstBlend ("DstBlend", Float) = 10.0

}
SubShader {
 Pass {
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 54034
}
}
SubShader {
 Pass {
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 98697
}
}
Fall back "Hidden/Internal-GUITextureClip"
}
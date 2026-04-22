//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-GUIRoundedRect" {
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
  GpuProgramID 3629
}
}
SubShader {
 Pass {
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 83701
}
}
Fall back "Hidden/Internal-GUITextureClip"
}
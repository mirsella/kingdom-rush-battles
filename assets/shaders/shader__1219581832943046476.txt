//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Legacy Shaders/VertexLit" {
Properties {

_Color ("Main Color", Color) = (1,1,1,1)

_SpecColor ("Spec Color", Color) = (1,1,1,1)

_Emission ("Emissive Color", Color) = (0,0,0,0)

[PowerSlider(5.0)] _Shininess ("Shininess", Range(0.01, 1)) = 0.699999988079071

_MainTex ("Base (RGB)", 2D) = "white" { }

}
SubShader {
 LOD 100
 Tags { "RenderType" = "Opaque" }
 Pass {
  LOD 100
  Tags { "LIGHTMODE" = "Vertex" "RenderType" = "Opaque" }
  GpuProgramID 176849
}
 Pass {
  LOD 100
  Tags { "LIGHTMODE" = "VertexLM" "RenderType" = "Opaque" }
  GpuProgramID 21925
}
 Pass {
 Name "ShadowCaster"
  LOD 100
  Tags { "LIGHTMODE" = "SHADOWCASTER" "RenderType" = "Opaque" "SHADOWSUPPORT" = "true" }
  GpuProgramID 94398
}
}
}
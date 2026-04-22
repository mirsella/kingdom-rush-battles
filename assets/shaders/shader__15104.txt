//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/CubeBlur" {
Properties {

_MainTex ("Main", Cube) = "" { }

_Texel ("Texel", Float) = 0.0078125

_Level ("Level", Float) = 0.0

_Scale ("Scale", Float) = 1.0

}
SubShader {
 LOD 200
 Tags { "RenderType" = "Opaque" }
 Pass {
  LOD 200
  Tags { "RenderType" = "Opaque" }
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 34126
}
}
SubShader {
 LOD 200
 Tags { "RenderType" = "Opaque" }
 Pass {
  LOD 200
  Tags { "RenderType" = "Opaque" }
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 80360
}
}
}
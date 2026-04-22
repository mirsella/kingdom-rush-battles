//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/CubeCopy" {
Properties {

_MainTex ("Main", Cube) = "" { }

_Level ("Level", Float) = 0.0

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
  GpuProgramID 46078
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
  GpuProgramID 115922
}
}
}
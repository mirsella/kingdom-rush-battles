//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/CubeBlend" {
Properties {

_TexA ("Cubemap", Cube) = "grey" { }

_TexB ("Cubemap", Cube) = "grey" { }

_value ("Value", Range(0, 1)) = 0.5

}
SubShader {
 Tags { "QUEUE" = "Background" "RenderType" = "Background" }
 Pass {
  Tags { "QUEUE" = "Background" "RenderType" = "Background" }
 ZTest Always
 ZWrite Off
  GpuProgramID 54436
}
}
SubShader {
 Tags { "QUEUE" = "Background" "RenderType" = "Background" }
 Pass {
  Tags { "QUEUE" = "Background" "RenderType" = "Background" }
 ZTest Always
 ZWrite Off
  GpuProgramID 120266
}
}
}
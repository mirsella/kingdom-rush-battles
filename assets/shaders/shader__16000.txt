//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/VideoComposite" {
Properties {

_MainTex ("_MainTex (A)", 2D) = "black" { }

}
SubShader {
 Tags { "QUEUE" = "Transparent" }
 Pass {
 Name "Default"
  Tags { "QUEUE" = "Transparent" }
 Cull Off
  GpuProgramID 10358
}
}
}
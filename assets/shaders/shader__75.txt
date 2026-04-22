//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/Internal-MotionVectors" {
Properties {

}
SubShader {
 Pass {
  Tags { "LIGHTMODE" = "MOTIONVECTORS" }
 ZWrite Off
  GpuProgramID 57106
}
 Pass {
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 71716
}
 Pass {
 ZTest Always
 Cull Off
  GpuProgramID 194660
}
}
}
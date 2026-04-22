//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Hidden/VideoDecode" {
Properties {

_MainTex ("_MainTex (A)", 2D) = "black" { }

_SecondTex ("_SecondTex (A)", 2D) = "black" { }

_ThirdTex ("_ThirdTex (A)", 2D) = "black" { }

}
SubShader {
 Pass {
 Name "YCbCr_To_RGB1"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 4092
}
 Pass {
 Name "YCbCrA_To_RGBAFull"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 102657
}
 Pass {
 Name "YCbCrA_To_RGBA"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 183317
}
 Pass {
 Name "Flip_RGBA_To_RGBA"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 207122
}
 Pass {
 Name "Flip_RGBASplit_To_RGBA"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 322832
}
 Pass {
 Name "Flip_NV12_To_RGB1"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 358349
}
 Pass {
 Name "Flip_NV12_To_RGBA"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 433943
}
 Pass {
 Name "Flip_P010_To_RGB1"
 ZTest Always
 ZWrite Off
 Cull Off
  GpuProgramID 522836
}
}
}
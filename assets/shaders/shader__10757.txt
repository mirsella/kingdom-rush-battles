//////////////////////////////////////////
//
// NOTE: This is *not* a valid shader file
//
///////////////////////////////////////////
Shader "Sprites/Mask" {
Properties {

_MainTex ("Sprite Texture", 2D) = "white" { }

_AlphaTex ("External Alpha", 2D) = "white" { }

_Cutoff ("Mask alpha cutoff", Range(0, 1)) = 0.0

_Color ("Tint", Color) = (1,1,1,0.2)

_EnableExternalAlpha ("Enable External Alpha", Float) = 0.0

[MaterialToggle] PixelSnap ("Pixel snap", Float) = 0.0

}
SubShader {
 Tags { "CanUseSpriteAtlas" = "true" "IGNOREPROJECTOR" = "true" "PreviewType" = "Plane" "QUEUE" = "Transparent" "RenderType" = "Transparent" }
 Pass {
  Tags { "CanUseSpriteAtlas" = "true" "IGNOREPROJECTOR" = "true" "PreviewType" = "Plane" "QUEUE" = "Transparent" "RenderType" = "Transparent" }
 ZWrite Off
 Cull Off
  GpuProgramID 38796
}
}
}
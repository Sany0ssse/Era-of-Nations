Includes = {
	"constants.fxh"
	"standardfuncsgfx.fxh"
	"pdxmap.fxh"
	"shadow.fxh"
	"tiled_pointlights.fxh"
	"fow.fxh"
}

PixelShader =
{
	Samplers =
	{
		HeightTexture =
		{
			Index = 0
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		LeanTexture1 =
		{
			Index = 1
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		LeanTexture2 =
		{
			Index = 2
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		ProvinceSecondaryColorMap =
		{
			Index = 3
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		SpecularMap =
		{
			Index = 4
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		WaterRefraction =
		{
			Index = 5
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		IceDiffuse =
		{
			Index = 6
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		IceNoise =
		{
			Index = 7
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		ReflectionCubeMap =
		{
			Index = 8
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
			Type = "Cube"
		}
		SnowMudTexture =
		{
			Index = 9
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		LightIndexMap =
		{
			Index = 10
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "Point"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		LightDataMap =
		{
			Index = 11
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "Point"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		GradientBorderChannel1 =
		{
			Index = 12
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		GradientBorderChannel2 =
		{
			Index = 13
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}		
		GradientBorderChannel3 =
		{
			Index = 14
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "Point"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		ShadowMap =
		{
			Index = 15
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
			Type = "Shadow"
		}
	}
}


VertexStruct VS_INPUT_WATER
{
    int2 position			: POSITION;
};

VertexStruct VS_OUTPUT_WATER
{
    float4 position			: PDX_POSITION;
	float3 pos				: TEXCOORD0; 
	float2 uv				: TEXCOORD1;
	float4 screen_pos		: TEXCOORD2; 
	float3 cubeRotation     : TEXCOORD3;
	float4 vShadowProj      : TEXCOORD4;	
	float4 vScreenCoord		: TEXCOORD5;
	float2 uv_ice			: TEXCOORD6;	
};


ConstantBuffer( 3, 48 )
{
	float3 vTime_HalfPixelOffset;
};



VertexShader =
{
	MainCode VertexShader
	[[
		VS_OUTPUT_WATER main( const VS_INPUT_WATER VertexIn )
		{
			VS_OUTPUT_WATER VertexOut;
			VertexOut.pos = float3( VertexIn.position.x, WATER_HEIGHT, VertexIn.position.y );
			VertexOut.position = mul( ViewProjectionMatrix, float4( VertexOut.pos.x, VertexOut.pos.y, VertexOut.pos.z, 1.0f ) );
			VertexOut.screen_pos = VertexOut.position;
			VertexOut.screen_pos.y = FIX_FLIPPED_UV( VertexOut.screen_pos.y );
			VertexOut.uv = float2( ( VertexIn.position.x + 0.5f ) / MAP_SIZE_X,  ( VertexIn.position.y + 0.5f - MAP_SIZE_Y ) / -MAP_SIZE_Y );
			VertexOut.uv *= float2( MAP_POW2_X, MAP_POW2_Y ); //POW2
			VertexOut.uv_ice = VertexOut.uv * float2( MAP_SIZE_X, MAP_SIZE_Y ) * 0.1f;
			VertexOut.uv_ice *= float2( FOW_POW2_X, FOW_POW2_Y ); //POW2
		
			float vAnimTime = vTime_HalfPixelOffset.x * 0.01f;
			VertexOut.cubeRotation = normalize( float3( sin( vAnimTime ) * 0.5f, sin( vAnimTime ), cos( vAnimTime ) * 0.3f ) );
			
			VertexOut.vShadowProj = mul( ShadowMapTextureMatrix, float4( VertexOut.pos, 1.0f ) );	
			
			// Output the screen-space texture coordinates
			VertexOut.vScreenCoord.x = ( VertexOut.position.x * 0.5 + VertexOut.position.w * 0.5 );
			VertexOut.vScreenCoord.y = ( VertexOut.position.w * 0.5 - VertexOut.position.y * 0.5 );
		#ifdef PDX_OPENGL
			VertexOut.vScreenCoord.y = -VertexOut.vScreenCoord.y;
		#endif			
			VertexOut.vScreenCoord.z = VertexOut.position.w;
			VertexOut.vScreenCoord.w = VertexOut.position.w;	
			
			return VertexOut;
		}
		
		
		
	]]
}

PixelShader =
{
	MainCode PixelShader
	[[
		// Custom dominance overlay: softer edges, starts at 50%, less pulsation.
		// Based on dominance_fx_apply from standardfuncsgfx.fxh (NOT copied -- redeclared under new name).
		void dominance_fx_apply_soft(inout float3 Color, float3 Normal, float2 UV, in sampler2D Texture1, in sampler2D Texture2, in sampler2D Texture3, float2 OutlineCutoff, float2 CameraDistOverride, float OutlineMult)
		{
			float HalfPix = 0.5f / GB_TextureHeight;
			float2 GBUV = float2(UV.x, UV.y * 0.5f - HalfPix);

			float4 Sample = tex2D( Texture2, GBUV );
			float4 ColorMask = float4(ToGamma(Sample.rgb),saturate(ceil(Sample.a*2)*0.5f));

			// --- Less pulsation: slower speeds, narrower ranges ---
			const float FadeSpeed = 0.5f;             // was 1.5
			const float ContestedPulseSpeed = 0.8f;   // was 2.5
			const float MinFade = 0.21f;              // was 0.2
			const float MaxFade = 0.23f;              // was 0.23

			float3 EnemyColor = tex2D(Texture3, float2(0,0)).rgb;
			float3 FriendlyColor = tex2D(Texture3, float2(1,0)).rgb;

			float Opacity = lerp( MinFade, MaxFade, ( sin( vGlobalTime * FadeSpeed ) + 1 ) * 0.5);
			// ContestedIntensity: narrowed range so contested regions don't flash as hard
			float ContestedIntensity = lerp( 1.0f, 1.15f, ( sin( vGlobalTime * ContestedPulseSpeed ) + 1 ) * 0.5);

			float ContestedBy = round(Sample.a) * ( Sample.a * 4.f - 3.f );
			float Control = round(ColorMask.r) * ( ColorMask.r * 4.f - 3.f );
			float3 OverlayColor = abs(Control)*lerp(EnemyColor, FriendlyColor, (Control + 1)/2);

			float4 GBDist =  gradient_border_multisample_alpha(tex2D( Texture1, GBUV ), Texture1, GBUV );
			float Alpha = GBDist.a;

			float IsRegionRelevant = saturate(abs(Control) + abs(ContestedBy))* (1- floor(Alpha));
			if (IsRegionRelevant < 0.99)
			{
				return;
			}

			float ColorOpacity = Levels( Alpha, 0.0f, OutlineCutoff.x );
			float Outline = 1.0f - Levels( Alpha,OutlineCutoff.x, 1.0f );
			float OldOutline = Outline;
			Outline *= floor(ColorOpacity);
			if (Outline > 0)
			{
				return;
			}
			Outline *= OutlineMult;

			float GBCamDist = gradient_border_camera_distance();
			float SaturatedCamDistOveride = saturate( ( GBCamDist * int( 1.0f - CameraDistOverride.x ) ) + CameraDistOverride.x );
			ColorOpacity = gradient_border_distance_to_alpha( ColorOpacity, SaturatedCamDistOveride );
			ColorOpacity *= floor(OldOutline);
			float MaxGradient = max(ColorOpacity,Outline);

			// --- Softer edges: smoothstep instead of hard linear cutoff ---
			// Диапазон 0.25...0.95 = широкая зона перехода. Сузишь -- границы станут жёстче.
		float OuterFade = 1.0f - smoothstep(0.0f, 0.85f, MaxGradient);

		if (abs(ContestedBy) > 0.7f)
		{
			float3 ContestedColor = lerp(EnemyColor, FriendlyColor, (ContestedBy + 1)/2);
			OverlayColor = lerp(OverlayColor, ContestedColor, 1.0f);

			// MaxGradient ≈ 0 в глубоком центре и растёт к краю региона.
			// CenterMask = 1 только у самого центра, быстро падает до 0 при MaxGradient > 0.33.
			// Значит гасим ТОЛЬКО центр, а переход к границе не трогаем.
			float CenterMask = 1.0f - saturate( MaxGradient * 3.0f );
			OuterFade *= lerp( 1.5f, 0.25f, CenterMask );
		}

		float Blend = Opacity * ( 0.0f + 1.0f * OuterFade );
		Color = lerp( Color, OverlayColor, Blend );
		}
		float3 ApplyIce( float3 vColor, float2 vPos, inout float3 vNormal, float4 vMudSnowColor, float2 vIceUV, out float vIceFade )
		{
			float4 vIceDiffuse = tex2D( IceDiffuse, vIceUV );
			float vIceNoise = tex2D( IceNoise, ( vPos + 0.5f ) * ICE_NOISE_TILING ).r;
		
			float vSnow = saturate( GetSnow( vMudSnowColor ) - 0.0f );
			

			vIceFade = vSnow*8.0f;
			vIceFade *= vIceNoise;

			float vOpacity = 1 - cam_distance( ICE_CAM_MIN, ICE_CAM_MAX );
			vIceFade *= vOpacity;

			// Code below will remove ice from certain parts of the world
			float vMapLimitFade = saturate( saturate( (vPos.y/MAP_SIZE_Y) - 0.74f )*800.0f );
			vIceFade *= vMapLimitFade;
			
			vIceFade = saturate( ( vIceFade-0.3f ) * 10.0f );
			vNormal = normalize( lerp( vNormal, normalize( vIceDiffuse.rbg - 0.5f ), vIceFade ) );
		
			float3 vIceColor = ICE_COLOR * vIceDiffuse.a;
			vColor = lerp( vColor, vIceColor, vIceFade );
		
			return vColor;
		}
		float MultiSampleTexX( in sampler2D TexCh, in float2 vUV )
		{
		#ifdef LOW_END_GFX
			return tex2D( TexCh, vUV ).x;
		#else
			float vOffsetX = -0.5f / MAP_SIZE_X;
			float vOffsetY = -0.5f / MAP_SIZE_Y;
			float vResult = tex2D( TexCh, vUV ).x;
			vResult += tex2D( TexCh, vUV + float2( -vOffsetX, 0 ) ).x;
			vResult += tex2D( TexCh, vUV + float2( 0, -vOffsetY ) ).x;
			vResult += tex2D( TexCh, vUV + float2( vOffsetX, 0 ) ).x;
			vResult += tex2D( TexCh, vUV + float2( 0, vOffsetY ) ).x;
			vResult += tex2D( TexCh, vUV + float2( -vOffsetX, -vOffsetY ) ).x;
			vResult += tex2D( TexCh, vUV + float2(  vOffsetX, -vOffsetY ) ).x;
			vResult += tex2D( TexCh, vUV + float2(  vOffsetX,  vOffsetY ) ).x;
			vResult += tex2D( TexCh, vUV + float2( -vOffsetX,  vOffsetY ) ).x;
			vResult /= 9;
			return vResult;
		#endif
		}
		
		float4 main( VS_OUTPUT_WATER Input ) : PDX_COLOR
		{
			//return float4( 0, 0, 1, 1 );
			float waterHeight = MultiSampleTexX( HeightTexture, Input.uv ) / ( 95.7f / 255.0f );
			float waterShore = saturate( ( waterHeight - 0.954f ) * 25.0f );
		
			float2 B;
			float3 M;
			float3 normal;
			SampleWater( Input.uv, vTime_HalfPixelOffset.x, B, M, normal, LeanTexture1, LeanTexture2 );
		
			float vSpecMap = tex2D( SpecularMap, Input.uv ).a;
			normal.y += ( 1.0f - vSpecMap );
			normal.xz *= vSpecMap;
			normal = normalize( normal );

			float vFlatten = vSpecMap;
			B *= vFlatten;
			M *= vFlatten * vFlatten;
		
		#ifdef LOW_END_GFX
			float3 SunDirWater = float3( 0, -1, 0 );
		#else
			float3 SunDirWater = CalculateSunDirectionWater( Input.pos );
		#endif
			float3 H = normalize( normalize(vCamPos - Input.pos).xzy + -SunDirWater.xzy );
			float2 HWave = H.xy/H.z - B;
		
			float3 sigma = M - float3( B*B, B.x*B.y);
			float det = sigma.x*sigma.y - sigma.z*sigma.z;
			float e = HWave.x*HWave.x*sigma.y + HWave.y*HWave.y*sigma.x - 2*HWave.x*HWave.y*sigma.z;
			float spec = (det <= 0) ? 0.0f : exp( -0.5f*e/det ) / sqrt(det);
			
			float2 refractiveUV = ( Input.screen_pos.xy / Input.screen_pos.w ) * 0.5f + 0.5f;
			refractiveUV.y = 1.0f - refractiveUV.y;
			refractiveUV += vTime_HalfPixelOffset.gb;
			float vRefractionScale = saturate( 5.0f - ( Input.screen_pos.z / Input.screen_pos.w ) * 5.0f );
		
			float2 vRefractionDistortion = normal.xz * vRefractionScale * 1.80f;
		
			float3 vEyeDir = normalize( Input.pos - vCamPos.xyz );
			float3 reflection = reflect( vEyeDir, normal );

			float vSpecularIntensity = 0.010f;
			float vGlossiness = (spec/9.0f) * (1-vSpecMap); 
			//float CubeMipmapIndex = GetEnvmapMipLevel(saturate(1.0f-vSpecMap)); 
			
			//float3 reflectiveColor = texCUBElod( ReflectionCubeMap, float4(reflection, CubeMipmapIndex) ).rgb;// * CubemapIntensity;
			float3 reflectiveColor = texCUBE( ReflectionCubeMap, reflection ).rgb;
		
		#ifdef NO_REFRACTIONS
			float3 refractiveColor = float3( 0, 0.1f, 0.2f );
		#else
			float3 refractiveColor = tex2D( WaterRefraction, refractiveUV.xy - vRefractionDistortion ).rgb;
		#endif

			float fresnelBias = 0.5f; // CUBEMAP INTENSITY
			float fresnel = saturate( dot( -vEyeDir, normal ) ) * 0.5f;
			fresnel = saturate( fresnelBias + ( 1.0f - fresnelBias ) * pow( 1.0f - fresnel, 10.0) );
			refractiveColor = refractiveColor * ( 1.0f - fresnel ) + reflectiveColor * fresnel;
			
			float vIceFade = 0.0f;
		#ifndef LOW_END_GFX
			float4 vMudSnowColor = GetMudSnowColor( Input.pos, SnowMudTexture );
			refractiveColor = ApplyIce( refractiveColor, Input.pos.xz, normal, vMudSnowColor, Input.uv_ice, vIceFade );

			vRefractionDistortion *= 1.0f - vIceFade;
			vSpecularIntensity += vIceFade * 0.07f;
			vGlossiness += vIceFade * 20.0f;
		#endif
		
			float vBloomAlpha = 0.0f;

			gradient_border_apply( refractiveColor, normal, 
				Input.uv + vRefractionDistortion * 0.0075f,
				GradientBorderChannel1, GradientBorderChannel2, 0.0f, 
				vGBCamDistOverride_GBOutlineCutoff.zw * GB_OUTLINE_CUTOFF_SEA,
				vGBCamDistOverride_GBOutlineCutoff.xy, vBloomAlpha );
			
			// darkness offset -- summary: 
			// when we fixed an old bug in the gradient border code, it made most mapmodes brighter. Players don't like that.
			// Therefore we offset the water a bit to make it more like what they're used to.
			float3 Darkness = float3(0,0,0); 
			refractiveColor = lerp(refractiveColor, Darkness, 0.2f);
			
			secondary_color_mask( refractiveColor, normal, 
				Input.uv - vRefractionDistortion * 0.001, 
				ProvinceSecondaryColorMap, 
				vBloomAlpha );

			LightingProperties lightingProperties;
			lightingProperties._WorldSpacePos = Input.pos;
			lightingProperties._ToCameraDir = normalize(vCamPos - Input.pos);
			lightingProperties._Normal = normal;
			lightingProperties._Diffuse = refractiveColor;
			lightingProperties._Glossiness = vGlossiness;
			lightingProperties._SpecularColor = vec3(vSpecularIntensity);
			lightingProperties._NonLinearGlossiness = GetNonLinearGlossiness(vGlossiness);
			
		
			// Grab the shadow term
		#ifdef LOW_END_GFX
			float3 diffuseLight = vec3(1.0f);
			float3 specularLight = vec3(0.002f);
		#else
			float3 diffuseLight = vec3(0.0);
			float3 specularLight = vec3(0.0);

			float4 vShadowCoord = Input.vScreenCoord;
			vShadowCoord.xz = vShadowCoord.xz + vRefractionDistortion * 20.0f;
			float fShadowTerm = GetShadowScaled( SHADOW_WEIGHT_WATER, vShadowCoord, ShadowMap );
		
			CalculateSunLight( lightingProperties, fShadowTerm, SunDirWater, diffuseLight, specularLight );

			CalculatePointLights( lightingProperties, LightDataMap, LightIndexMap, diffuseLight, specularLight);
		#endif

			float3 vOut = ComposeLight(lightingProperties, diffuseLight, specularLight);
		
		#ifndef LOW_END_GFX
			vOut = ApplyFOW( vOut, ShadowMap, Input.vScreenCoord );
			vOut = ApplyDistanceFog( vOut, Input.pos );
		#endif

			vOut = DayNightWithBlend( vOut, CalcGlobeNormal( Input.pos.xz ), lerp(BORDER_NIGHT_DESATURATION_MAX, 1.0f, vBloomAlpha) );
			
			dominance_fx_apply_soft(vOut, normal, 
				Input.uv, 
				GradientBorderChannel1,GradientBorderChannel2,GradientBorderChannel3,
				vGBCamDistOverride_GBOutlineCutoff.zw * GB_OUTLINE_CUTOFF_SEA,vGBCamDistOverride_GBOutlineCutoff.xy, 0.0f);
				
		#ifdef LOW_END_GFX
			DebugReturn(vOut, lightingProperties, 0.0f);
		#else
			DebugReturn(vOut, lightingProperties, fShadowTerm);
		#endif
			return float4( vOut, 1.0f - waterShore );
		}
	]]
}


BlendState BlendState
{
	BlendEnable = yes
	AlphaTest = no
	SourceBlend = "src_alpha"
	DestBlend = "inv_src_alpha"
	WriteMask = "RED|GREEN|BLUE"
}

Effect water_low_gfx
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
	Defines = { "LOW_END_GFX" "NO_REFRACTIONS" }
}

Effect water_no_refractions
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
	Defines = { "NO_REFRACTIONS" }
}

Effect water
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
}



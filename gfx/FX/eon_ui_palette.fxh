# Era of Nations: opt-in graphite/navy palette for interface chrome only.
# Texture data, alpha, neutral text, red and green are not changed by this function.
# Apply once to the finished source/animation color before native button-state operations.
Code
[[
float4 EonUIApplyPalette(float4 SourceColor)
{
    float3 SourceRGB = SourceColor.rgb;
    float Peak = max(max(SourceRGB.r, SourceRGB.g), SourceRGB.b);
    float Lowest = min(min(SourceRGB.r, SourceRGB.g), SourceRGB.b);
    float SafePeak = max(Peak, 0.0001);

    // Include soft lavender panel gradients while excluding neutral grayscale.
    float ChromaMask = smoothstep(0.035, 0.08, (Peak - Lowest) / SafePeak);
    // Blue relative to green selects both deep indigo and pale lavender, not green/cyan.
    float CoolMask = smoothstep(0.035, 0.075, (SourceRGB.b - SourceRGB.g) / SafePeak);
    // Red-dominant warnings and green-dominant status pixels remain untouched.
    float PurpleMask = smoothstep(-0.10, 0.00, (SourceRGB.b - SourceRGB.r) / SafePeak);
    // Protect white and near-white text, including lightly compressed bright pixels.
    float WhiteProtection = 1.0 - smoothstep(0.72, 0.78, Lowest);
    float PaletteMask = ChromaMask * CoolMask * PurpleMask * WhiteProtection;

    // Keep the source brightness gradient; cap its colored glow at a muted steel-blue tone.
    float3 GraphiteBlue = Peak * float3(0.35, 0.47, 0.64);
    SourceColor.rgb = lerp(SourceRGB, GraphiteBlue, PaletteMask);
    return SourceColor;
}
]]

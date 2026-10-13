# Era of Nations: semantic colors for national focus titlebars only.
# Keep the source shading, alpha, shape, masks and native animations.
# Focus names and country illustrations are separate UI objects.
Code
[[
float4 EonFocusStateColor(float4 SourceColor, float3 StateTone)
{
    float Peak = max(max(SourceColor.r, SourceColor.g), SourceColor.b);
    SourceColor.rgb = Peak * StateTone;
    return SourceColor;
}
]]

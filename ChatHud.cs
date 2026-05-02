using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Menus;

namespace NagiBridge;

public class ChatMessage
{
    public string Sender { get; set; } = "";
    public string Text { get; set; } = "";
    public DateTime Time { get; set; } = DateTime.Now;
    public bool IsPlayer => Sender != "Nagi";
}

public class ChatHud
{
    private readonly List<ChatMessage> _messages = new();
    private bool _isOpen;
    private string _inputText = "";
    private int _scrollOffset;
    private int _cursorBlink;
    private const int MaxHistory = 50;
    private const int VisibleMessages = 10;
    private const int HudVisibleMessages = 2;

    private KeyboardState _prevKeyState;
    private MouseState _prevMouseState;

    private readonly IMonitor _monitor;
    private readonly Action<string>? _onSend;

    public ChatHud(IMonitor monitor, Action<string>? onSend = null)
    {
        _monitor = monitor;
        _onSend = onSend;
    }

    public bool IsOpen => _isOpen;

    public void AddMessage(string sender, string text)
    {
        _messages.Add(new ChatMessage { Sender = sender, Text = text });
        if (_messages.Count > MaxHistory)
            _messages.RemoveAt(0);
        _scrollOffset = 0;
    }

    public void Toggle()
    {
        _isOpen = !_isOpen;
        if (_isOpen)
            _scrollOffset = 0;
    }

    public void Update()
    {
        if (Context.IsMultiplayer) return;

        var keyState = Keyboard.GetState();
        var mouseState = Mouse.GetState();

        bool justOpened = false;
        if (keyState.IsKeyDown(Keys.T) && !_prevKeyState.IsKeyDown(Keys.T)
            && !_isOpen && Game1.activeClickableMenu == null)
        {
            _isOpen = true;
            _scrollOffset = 0;
            justOpened = true;
        }
        else if (keyState.IsKeyDown(Keys.Escape) && !_prevKeyState.IsKeyDown(Keys.Escape) && _isOpen)
        {
            _isOpen = false;
            _inputText = "";
        }

        if (_isOpen && !justOpened)
        {
            HandleInput(keyState);
            HandleScroll(mouseState);
        }

        _cursorBlink = (_cursorBlink + 1) % 60;
        _prevKeyState = keyState;
        _prevMouseState = mouseState;
    }

    private void HandleInput(KeyboardState keyState)
    {
        if (keyState.IsKeyDown(Keys.Enter) && !_prevKeyState.IsKeyDown(Keys.Enter))
        {
            if (!string.IsNullOrWhiteSpace(_inputText))
            {
                var text = _inputText.Trim();
                AddMessage("You", text);
                _onSend?.Invoke(text);
                _inputText = "";
            }
            return;
        }

        if (keyState.IsKeyDown(Keys.Back) && !_prevKeyState.IsKeyDown(Keys.Back))
        {
            if (_inputText.Length > 0)
                _inputText = _inputText[..^1];
            return;
        }

        foreach (var key in keyState.GetPressedKeys())
        {
            if (_prevKeyState.IsKeyDown(key)) continue;
            if (key == Keys.Enter || key == Keys.Back || key == Keys.Escape) continue;
            if (key == Keys.LeftShift || key == Keys.RightShift) continue;
            if (key == Keys.LeftControl || key == Keys.RightControl) continue;

            char? c = KeyToChar(key, keyState.IsKeyDown(Keys.LeftShift) || keyState.IsKeyDown(Keys.RightShift));
            if (c.HasValue && _inputText.Length < 200)
                _inputText += c.Value;
        }
    }

    private void HandleScroll(MouseState mouseState)
    {
        int scrollDelta = mouseState.ScrollWheelValue - _prevMouseState.ScrollWheelValue;
        if (scrollDelta > 0 && _scrollOffset < _messages.Count - VisibleMessages)
            _scrollOffset++;
        else if (scrollDelta < 0 && _scrollOffset > 0)
            _scrollOffset--;
    }

    public void DrawHud(SpriteBatch b)
    {
        if (Context.IsMultiplayer || _isOpen || _messages.Count == 0) return;

        var recent = _messages.TakeLast(HudVisibleMessages).ToList();
        var font = Game1.smallFont;
        int y = Game1.viewport.Height - 160;
        int x = 20;
        int maxWidth = 400;

        foreach (var msg in recent)
        {
            string display = $"{msg.Sender}: {msg.Text}";
            var wrapped = WrapText(font, display, maxWidth);
            var size = font.MeasureString(wrapped);

            DrawBox(b, x - 8, y - 4, (int)size.X + 16, (int)size.Y + 8, 0.6f);
            b.DrawString(font, wrapped, new Vector2(x, y),
                msg.IsPlayer ? Color.White : Color.LightCyan,
                0f, Vector2.Zero, 1f, SpriteEffects.None, 1f);
            y += (int)size.Y + 12;
        }
    }

    public void DrawPanel(SpriteBatch b)
    {
        if (!_isOpen || Context.IsMultiplayer) return;

        var font = Game1.smallFont;
        int panelWidth = 460;
        int lineHeight = 26;
        int padding = 12;

        var visible = GetVisibleMessages();
        int msgLines = 0;
        foreach (var msg in visible)
        {
            string display = $"[{msg.Time:HH:mm}] {msg.Sender}: {msg.Text}";
            var wrapped = WrapText(font, display, panelWidth - 32);
            msgLines += wrapped.Split('\n').Length;
        }
        int minMsgLines = 3;
        msgLines = Math.Max(msgLines, minMsgLines);

        int titleHeight = 30;
        int msgAreaHeight = msgLines * lineHeight + padding;
        int inputHeight = 36;
        int helpHeight = 18;
        int panelHeight = titleHeight + msgAreaHeight + inputHeight + helpHeight + padding;

        int panelX = (Game1.viewport.Width - panelWidth) / 2;
        int panelY = Game1.viewport.Height - panelHeight - 20;

        DrawBox(b, panelX, panelY, panelWidth, panelHeight, 0.88f);

        b.DrawString(font, "Chat", new Vector2(panelX + 16, panelY + 8), Color.Gold,
            0f, Vector2.Zero, 1f, SpriteEffects.None, 1f);

        int msgAreaTop = panelY + titleHeight;
        int drawY = msgAreaTop;

        foreach (var msg in visible)
        {
            string display = $"[{msg.Time:HH:mm}] {msg.Sender}: {msg.Text}";
            var wrapped = WrapText(font, display, panelWidth - 32);
            var lines = wrapped.Split('\n');

            foreach (var line in lines)
            {
                if (drawY + lineHeight > msgAreaTop + msgAreaHeight) break;
                b.DrawString(font, line, new Vector2(panelX + 16, drawY),
                    msg.IsPlayer ? Color.White : Color.LightCyan,
                    0f, Vector2.Zero, 1f, SpriteEffects.None, 1f);
                drawY += lineHeight;
            }
        }

        // Scroll indicator
        if (_messages.Count > VisibleMessages)
        {
            string scrollInfo = $"↑{_scrollOffset} / {_messages.Count}";
            b.DrawString(font, scrollInfo, new Vector2(panelX + panelWidth - 100, panelY + 8),
                Color.Gray, 0f, Vector2.Zero, 0.8f, SpriteEffects.None, 1f);
        }

        // Input box
        int inputY = panelY + panelHeight - inputHeight - helpHeight;
        DrawBox(b, panelX + 8, inputY, panelWidth - 16, 30, 0.95f);

        string cursor = (_cursorBlink < 30) ? "|" : "";
        string inputDisplay = _inputText + cursor;
        b.DrawString(font, inputDisplay, new Vector2(panelX + 16, inputY + 5), Color.White,
            0f, Vector2.Zero, 1f, SpriteEffects.None, 1f);

        // Help text
        b.DrawString(font, "Enter=Send  Esc=Close  Scroll=History",
            new Vector2(panelX + 16, panelY + panelHeight - helpHeight),
            Color.Gray, 0f, Vector2.Zero, 0.7f, SpriteEffects.None, 1f);
    }

    private List<ChatMessage> GetVisibleMessages()
    {
        if (_messages.Count == 0) return new();
        int start = Math.Max(0, _messages.Count - VisibleMessages - _scrollOffset);
        int count = Math.Min(VisibleMessages, _messages.Count - start);
        return _messages.GetRange(start, count);
    }

    private static void DrawBox(SpriteBatch b, int x, int y, int w, int h, float alpha)
    {
        var pixel = Game1.staminaRect;
        b.Draw(pixel, new Microsoft.Xna.Framework.Rectangle(x, y, w, h),
            Color.Black * alpha);
        // Border
        b.Draw(pixel, new Microsoft.Xna.Framework.Rectangle(x, y, w, 1), Color.Gray * 0.8f);
        b.Draw(pixel, new Microsoft.Xna.Framework.Rectangle(x, y + h - 1, w, 1), Color.Gray * 0.8f);
        b.Draw(pixel, new Microsoft.Xna.Framework.Rectangle(x, y, 1, h), Color.Gray * 0.8f);
        b.Draw(pixel, new Microsoft.Xna.Framework.Rectangle(x + w - 1, y, 1, h), Color.Gray * 0.8f);
    }

    private static string WrapText(SpriteFont font, string text, int maxWidth)
    {
        if (font.MeasureString(text).X <= maxWidth)
            return text;

        var sb = new StringBuilder();
        var words = text.Split(' ');
        float lineWidth = 0;
        float spaceWidth = font.MeasureString(" ").X;

        foreach (var word in words)
        {
            var wordWidth = font.MeasureString(word).X;
            if (lineWidth + wordWidth > maxWidth && lineWidth > 0)
            {
                sb.AppendLine();
                lineWidth = 0;
            }
            if (lineWidth > 0)
            {
                sb.Append(' ');
                lineWidth += spaceWidth;
            }
            sb.Append(word);
            lineWidth += wordWidth;
        }
        return sb.ToString();
    }

    private static char? KeyToChar(Keys key, bool shift)
    {
        if (key >= Keys.A && key <= Keys.Z)
            return shift ? (char)('A' + key - Keys.A) : (char)('a' + key - Keys.A);
        if (key >= Keys.D0 && key <= Keys.D9 && !shift)
            return (char)('0' + key - Keys.D0);
        return key switch
        {
            Keys.Space => ' ',
            Keys.OemPeriod => shift ? '>' : '.',
            Keys.OemComma => shift ? '<' : ',',
            Keys.OemQuestion => shift ? '?' : '/',
            Keys.OemMinus => shift ? '_' : '-',
            Keys.OemPlus => shift ? '+' : '=',
            Keys.D1 when shift => '!',
            Keys.D2 when shift => '@',
            Keys.D3 when shift => '#',
            Keys.D4 when shift => '$',
            Keys.D5 when shift => '%',
            Keys.D6 when shift => '^',
            Keys.D7 when shift => '&',
            Keys.D8 when shift => '*',
            Keys.D9 when shift => '(',
            Keys.D0 when shift => ')',
            _ => null
        };
    }
}

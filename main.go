package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"

	"github.com/go-telegram/bot"
	"github.com/go-telegram/bot/models"
	"github.com/joho/godotenv"
)

func main() {
	// Load environment variables from .env file
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: Error loading .env file: %v", err)
	}

	// Get bot token from environment variable
	token := os.Getenv("BOT_TOKEN")
	if token == "" {
		log.Fatal("BOT_TOKEN environment variable is required")
	}

	// Create a new bot instance
	b, err := bot.New(token)
	if err != nil {
		log.Fatal(err)
	}

	// Create a context that will be canceled on interrupt
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()

	// Register command handlers
	b.RegisterHandler(bot.HandlerTypeMessageText, "/start", bot.MatchTypeExact, func(ctx context.Context, b *bot.Bot, update *models.Update) {
		handleStart(ctx, b, update)
	})
	b.RegisterHandler(bot.HandlerTypeMessageText, "/menu", bot.MatchTypeExact, func(ctx context.Context, b *bot.Bot, update *models.Update) {
		handleMenu(ctx, b, update)
	})
	// Register callback query handler for buttons
	b.RegisterHandler(bot.HandlerTypeCallbackQueryData, "", bot.MatchTypePrefix, func(ctx context.Context, b *bot.Bot, update *models.Update) {
		handleCallback(ctx, b, update)
	})

	log.Printf("Starting bot...")
	b.Start(ctx)
}

func handleStart(ctx context.Context, b *bot.Bot, update *models.Update) error {
	keyboard := [][]models.InlineKeyboardButton{
		{
			{Text: "📱 Open Menu", CallbackData: "menu_main"},
		},
	}

	welcomeMsg := "👋 Welcome! This is an interactive menu bot.\n\n" +
		"Click the button below to open the main menu, or use /menu command."

	_, err := b.SendMessage(ctx, &bot.SendMessageParams{
		ChatID:      update.Message.Chat.ID,
		Text:        welcomeMsg,
		ReplyMarkup: &models.InlineKeyboardMarkup{InlineKeyboard: keyboard},
	})
	return err
}

func handleMenu(ctx context.Context, b *bot.Bot, update *models.Update) error {
	return showMainMenu(ctx, b, update.Message.Chat.ID)
}

func handleCallback(ctx context.Context, b *bot.Bot, update *models.Update) {
	if update.CallbackQuery == nil {
		return
	}

	// Get chat ID from the callback query message
	msg := update.CallbackQuery.Message.Message
	if msg == nil {
		log.Printf("Warning: Callback query message is nil")
		return
	}

	chatID := msg.Chat.ID

	// Answer the callback query to remove the loading state
	b.AnswerCallbackQuery(ctx, &bot.AnswerCallbackQueryParams{
		CallbackQueryID: update.CallbackQuery.ID,
	})

	switch update.CallbackQuery.Data {
	case "menu_main":
		showMainMenu(ctx, b, chatID)
	case "menu_subscriptions":
		showSubscriptions(ctx, b, chatID)
	case "menu_profile":
		// Create a pointer to the From user for profile
		from := update.CallbackQuery.From
		showProfile(ctx, b, chatID, &from)
	case "menu_back":
		showMainMenu(ctx, b, chatID)
	case "sub_basic", "sub_premium", "sub_pro":
		handleSubscription(ctx, b, chatID, update.CallbackQuery.Data)
	}
}

func showMainMenu(ctx context.Context, b *bot.Bot, chatID int64) error {
	keyboard := [][]models.InlineKeyboardButton{
		{
			{Text: "📱 Subscriptions", CallbackData: "menu_subscriptions"},
		},
		{
			{Text: "👤 My Profile", CallbackData: "menu_profile"},
		},
	}

	_, err := b.SendMessage(ctx, &bot.SendMessageParams{
		ChatID:      chatID,
		Text:        "📋 Main Menu - Select an option:",
		ReplyMarkup: &models.InlineKeyboardMarkup{InlineKeyboard: keyboard},
	})
	return err
}

func showSubscriptions(ctx context.Context, b *bot.Bot, chatID int64) error {
	keyboard := [][]models.InlineKeyboardButton{
		{
			{Text: "Basic - $9.99/mo", CallbackData: "sub_basic"},
		},
		{
			{Text: "Premium - $19.99/mo", CallbackData: "sub_premium"},
		},
		{
			{Text: "Pro - $29.99/mo", CallbackData: "sub_pro"},
		},
		{
			{Text: "⬅️ Back to Menu", CallbackData: "menu_back"},
		},
	}

	_, err := b.SendMessage(ctx, &bot.SendMessageParams{
		ChatID:      chatID,
		Text:        "📱 Subscription Plans:",
		ReplyMarkup: &models.InlineKeyboardMarkup{InlineKeyboard: keyboard},
	})
	return err
}

func showProfile(ctx context.Context, b *bot.Bot, chatID int64, user *models.User) error {
	keyboard := [][]models.InlineKeyboardButton{
		{
			{Text: "⬅️ Back to Menu", CallbackData: "menu_back"},
		},
	}

	profileText := fmt.Sprintf("👤 User Profile\n\n"+
		"ID: %d\n"+
		"Name: %s\n"+
		"Username: @%s\n"+
		"Language: %s",
		user.ID,
		user.FirstName,
		user.Username,
		user.LanguageCode)

	_, err := b.SendMessage(ctx, &bot.SendMessageParams{
		ChatID:      chatID,
		Text:        profileText,
		ReplyMarkup: &models.InlineKeyboardMarkup{InlineKeyboard: keyboard},
	})
	return err
}

func handleSubscription(ctx context.Context, b *bot.Bot, chatID int64, subID string) error {
	prices := map[string]float64{
		"sub_basic":   9.99,
		"sub_premium": 19.99,
		"sub_pro":     29.99,
	}

	plans := map[string]string{
		"sub_basic":   "Basic",
		"sub_premium": "Premium",
		"sub_pro":     "Pro",
	}

	keyboard := [][]models.InlineKeyboardButton{
		{
			{Text: "⬅️ Back to Subscriptions", CallbackData: "menu_subscriptions"},
		},
	}

	text := fmt.Sprintf("Selected Plan: %s\nMonthly Price: $%.2f\n\nTo subscribe, please contact our support.", plans[subID], prices[subID])

	_, err := b.SendMessage(ctx, &bot.SendMessageParams{
		ChatID:      chatID,
		Text:        text,
		ReplyMarkup: &models.InlineKeyboardMarkup{InlineKeyboard: keyboard},
	})
	return err
}

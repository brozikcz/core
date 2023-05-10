"""Test tts."""
from __future__ import annotations

import io
from unittest.mock import patch
import wave

import pytest
from wyoming.audio import AudioChunk, AudioStop

from homeassistant.components import tts
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES

from . import MockAsyncTcpClient

from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    init_cache_dir_side_effect,
    mock_get_cache_files,
    mock_init_cache_dir,
)


async def test_support(hass: HomeAssistant, init_wyoming_tts) -> None:
    """Test supported properties."""
    state = hass.states.get("tts.test_tts")
    assert state is not None

    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None

    assert entity.supported_languages == ["en-US"]
    assert entity.supported_options == [tts.ATTR_AUDIO_OUTPUT, tts.ATTR_VOICE]
    assert entity.default_language == "en-US"
    voices = entity.async_get_supported_voices("en-US")
    assert len(voices) == 1
    assert voices[0].name == "Test Voice"
    assert voices[0].voice_id == "Test Voice"
    assert not entity.async_get_supported_voices("de-DE")


async def test_no_options(hass: HomeAssistant, init_wyoming_tts, snapshot) -> None:
    """Test options=None."""
    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    state = hass.states.get("tts.test_tts")
    assert state is not None

    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await entity.async_get_tts_audio(
            "Hello world", "en-US", options=None
        )

        assert extension == "mp3"
        assert data is not None
        assert mock_client.written == snapshot


async def test_get_tts_audio(hass: HomeAssistant, init_wyoming_tts, snapshot) -> None:
    """Test get audio."""
    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(hass, "Hello world", "tts.test_tts", "en-US"),
        )

        assert extension == "mp3"
        assert data is not None
        assert mock_client.written == snapshot


@pytest.mark.parametrize(
    "audio_format",
    [("wav",), ("raw",)],
)
async def test_get_tts_audio_format(
    hass: HomeAssistant, init_wyoming_tts, snapshot, audio_format: str
) -> None:
    """Test get audio in a specific format."""
    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass,
                "Hello world",
                "tts.test_tts",
                "en-US",
                options={tts.ATTR_AUDIO_OUTPUT: audio_format},
            ),
        )

    assert extension == audio_format

    if audio_format == "raw":
        assert data == audio
    else:
        # Verify WAV audio
        with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
            assert wav_file.getframerate() == 16000
            assert wav_file.getsampwidth() == 2
            assert wav_file.getnchannels() == 1
            assert wav_file.readframes(wav_file.getnframes()) == audio

    assert mock_client.written == snapshot


async def test_get_tts_audio_connection_lost(
    hass: HomeAssistant, init_wyoming_tts
) -> None:
    """Test streaming audio and losing connection."""
    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ), pytest.raises(HomeAssistantError):
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(hass, "Hello world", "tts.test_tts", "en-US"),
        )


async def test_get_tts_audio_audio_oserror(
    hass: HomeAssistant, init_wyoming_tts
) -> None:
    """Test get audio and error raising."""
    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    mock_client = MockAsyncTcpClient(audio_events)

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        mock_client,
    ), patch.object(
        mock_client, "read_event", side_effect=OSError("Boom!")
    ), pytest.raises(
        HomeAssistantError
    ):
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(hass, "Hello world", "tts.test_tts", "en-US"),
        )
